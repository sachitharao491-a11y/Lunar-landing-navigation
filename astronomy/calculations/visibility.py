"""
visibility.py — Geometric visibility determination
====================================================

Determines whether the Sun and Earth are geometrically visible from a
lunar surface site, accounting for the finite angular size of each body's
disk.

IMPORTANT SCIENTIFIC DISTINCTIONS
----------------------------------
1. **Geometric visibility** (this module) considers only the angular
   position of a body relative to the mathematical horizon plane
   perpendicular to the local zenith.  It does NOT account for terrain
   obstructions (craters, ridges, mountains).

2. **Terrain-aware visibility** would require LOLA digital elevation
   model data and ray-casting against the local topography.  That is
   out of scope for this module.

3. The Moon has **no atmosphere**, so there is no atmospheric refraction.
   The geometric horizon is the true visual horizon (unlike on Earth
   where refraction lifts objects ~0.57° above the geometric horizon).

Visibility states
-----------------
    FULLY_VISIBLE     : Entire disk is above the geometric horizon.
    PARTIALLY_VISIBLE : Disk straddles the horizon — upper limb visible,
                        lower limb below.  The observer would see a
                        partial disk.
    NOT_VISIBLE       : Entire disk is below the geometric horizon.

Angular radii (as seen from the Moon)
-------------------------------------
    Sun  : ~0.267°  (695,700 km radius at ~1 AU)
    Earth: ~0.95°   (6,371 km radius at ~384,400 km mean distance)

    Earth's angular radius varies with distance (356k–407k km), so we
    compute it dynamically from the Horizons range when available.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import numpy as np

from astronomy.api.config import EARTH_ID, SUN_ID
from astronomy.api.horizons_client import query_body, query_body_range
from astronomy.models.landing_site import CelestialResult, LandingSite

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

# Physical radii (km)
SUN_RADIUS_KM = 695_700.0
EARTH_RADIUS_KM = 6_371.0

# Fallback angular radii (degrees) when range is not available
SUN_DEFAULT_ANGULAR_RADIUS_DEG = 0.267
EARTH_DEFAULT_ANGULAR_RADIUS_DEG = 0.95


# ═══════════════════════════════════════════════════════════════════════
# Visibility state enumeration
# ═══════════════════════════════════════════════════════════════════════

class VisibilityState(str, Enum):
    """
    Geometric visibility classification for a celestial body.

    The state accounts for the body's finite angular disk, not just
    its center point.
    """
    FULLY_VISIBLE = "fully_visible"
    PARTIALLY_VISIBLE = "partially_visible"
    NOT_VISIBLE = "not_visible"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════
# Visibility result model
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class VisibilityResult:
    """
    Complete geometric visibility assessment for one body at one instant.

    Attributes
    ----------
    body_name            : "Sun" or "Earth"
    datetime_utc         : Observation time
    site                 : Observer location
    state                : Visibility classification
    elevation_deg        : Center elevation above horizon (degrees)
    azimuth_deg          : Azimuth (degrees, 0=N clockwise)
    angular_radius_deg   : Apparent angular radius of the body (degrees)
    upper_limb_elevation_deg : Elevation of the top edge of the disk
    lower_limb_elevation_deg : Elevation of the bottom edge of the disk
    visible_fraction     : Fraction of the disk above the horizon (0–1)
    range_km             : Distance to the body (km)
    is_geometric_only    : Always True — reminder that terrain is not considered
    """
    body_name: str
    datetime_utc: datetime
    site: LandingSite
    state: VisibilityState
    elevation_deg: Optional[float]
    azimuth_deg: Optional[float]
    angular_radius_deg: float
    upper_limb_elevation_deg: Optional[float]
    lower_limb_elevation_deg: Optional[float]
    visible_fraction: Optional[float]
    range_km: Optional[float]
    is_geometric_only: bool = True

    def to_dict(self) -> dict:
        return {
            "body_name": self.body_name,
            "datetime_utc": self.datetime_utc.isoformat(),
            "site": {
                "name": self.site.name,
                "latitude_deg": self.site.latitude,
                "longitude_deg_east": self.site.longitude,
            },
            "state": self.state.value,
            "elevation_deg": self.elevation_deg,
            "azimuth_deg": self.azimuth_deg,
            "angular_radius_deg": round(self.angular_radius_deg, 6),
            "upper_limb_elevation_deg": self.upper_limb_elevation_deg,
            "lower_limb_elevation_deg": self.lower_limb_elevation_deg,
            "visible_fraction": (
                round(self.visible_fraction, 4)
                if self.visible_fraction is not None else None
            ),
            "range_km": self.range_km,
            "is_geometric_only": self.is_geometric_only,
            "note": (
                "Geometric visibility only. Does not account for terrain "
                "obstructions (craters, ridges). No atmospheric refraction "
                "(Moon is airless)."
            ),
        }


# ═══════════════════════════════════════════════════════════════════════
# Horizon-crossing event
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class HorizonEvent:
    """
    A rise or set event — the moment a body's upper limb crosses the
    geometric horizon.

    Attributes
    ----------
    event_type        : "rise" or "set"
    datetime_utc      : Estimated time of the event (interpolated)
    body_name         : "Sun" or "Earth"
    site              : Observer location
    azimuth_deg       : Azimuth at the time of the event
    interpolation_note: How the time was estimated
    """
    event_type: str  # "rise" or "set"
    datetime_utc: datetime
    body_name: str
    site: LandingSite
    azimuth_deg: Optional[float]
    interpolation_note: str = "linear interpolation between adjacent steps"

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "datetime_utc": self.datetime_utc.isoformat(),
            "body_name": self.body_name,
            "site": {
                "name": self.site.name,
                "latitude_deg": self.site.latitude,
                "longitude_deg_east": self.site.longitude,
            },
            "azimuth_deg": self.azimuth_deg,
            "interpolation_note": self.interpolation_note,
        }


# ═══════════════════════════════════════════════════════════════════════
# 1.  Angular radius computation
# ═══════════════════════════════════════════════════════════════════════

def compute_angular_radius(
    body_physical_radius_km: float,
    range_km: Optional[float],
    default_deg: float,
) -> float:
    """
    Compute the apparent angular radius of a body from its physical
    radius and distance.

    Parameters
    ----------
    body_physical_radius_km : True physical radius of the body (km).
    range_km                : Observer-to-body distance (km).
    default_deg             : Fallback angular radius if range is None.

    Returns
    -------
    Angular radius in degrees.
    """
    if range_km is None or range_km <= 0:
        return default_deg
    return math.degrees(math.atan2(body_physical_radius_km, range_km))


# ═══════════════════════════════════════════════════════════════════════
# 2.  Visible fraction of disk above horizon
# ═══════════════════════════════════════════════════════════════════════

def compute_visible_fraction(
    center_elevation_deg: float,
    angular_radius_deg: float,
) -> float:
    """
    Estimate the fraction of a circular disk that is above the horizon.

    Uses the geometric formula for the area of a circular segment.
    This is an approximation (assumes the horizon is a straight line
    across the disk, which is excellent for small angular radii).

    Parameters
    ----------
    center_elevation_deg : Elevation of the disk center (degrees).
    angular_radius_deg   : Angular radius of the disk (degrees).

    Returns
    -------
    Fraction visible (0.0 to 1.0).
    """
    if angular_radius_deg <= 0:
        return 1.0 if center_elevation_deg > 0 else 0.0

    # How far the center is above the horizon, normalised by radius
    h = center_elevation_deg / angular_radius_deg

    if h >= 1.0:
        return 1.0  # Entire disk above
    if h <= -1.0:
        return 0.0  # Entire disk below

    # Fraction of circular disk above a chord at height h (from center)
    # where h ∈ [-1, 1] is normalised by radius.
    # Area above = (1/π) * [arccos(-h) + h * sqrt(1 - h²)]
    # (This is the standard circular segment area formula)
    fraction = (1.0 / math.pi) * (
        math.acos(-h) + h * math.sqrt(1.0 - h * h)
    )
    return max(0.0, min(1.0, fraction))


# ═══════════════════════════════════════════════════════════════════════
# 3.  Classify visibility state
# ═══════════════════════════════════════════════════════════════════════

def classify_visibility(
    elevation_deg: Optional[float],
    angular_radius_deg: float,
) -> VisibilityState:
    """
    Classify visibility based on center elevation and angular radius.
    """
    if elevation_deg is None:
        return VisibilityState.UNKNOWN

    upper_limb = elevation_deg + angular_radius_deg
    lower_limb = elevation_deg - angular_radius_deg

    if lower_limb >= 0.0:
        return VisibilityState.FULLY_VISIBLE
    elif upper_limb > 0.0:
        return VisibilityState.PARTIALLY_VISIBLE
    else:
        return VisibilityState.NOT_VISIBLE


# ═══════════════════════════════════════════════════════════════════════
# 4.  Build a VisibilityResult from a CelestialResult
# ═══════════════════════════════════════════════════════════════════════

def assess_visibility(
    result: CelestialResult,
    body_radius_km: float,
    default_angular_radius_deg: float,
) -> VisibilityResult:
    """
    Assess geometric visibility from a parsed Horizons result.

    Parameters
    ----------
    result                     : CelestialResult from the API client.
    body_radius_km             : Physical radius of the body (km).
    default_angular_radius_deg : Fallback angular radius if range unknown.

    Returns
    -------
    VisibilityResult with full disk-aware classification.
    """
    ang_radius = compute_angular_radius(
        body_radius_km, result.range_km, default_angular_radius_deg
    )

    state = classify_visibility(result.elevation_deg, ang_radius)

    upper_limb = (
        result.elevation_deg + ang_radius
        if result.elevation_deg is not None else None
    )
    lower_limb = (
        result.elevation_deg - ang_radius
        if result.elevation_deg is not None else None
    )

    visible_fraction = (
        compute_visible_fraction(result.elevation_deg, ang_radius)
        if result.elevation_deg is not None else None
    )

    return VisibilityResult(
        body_name=result.target_body,
        datetime_utc=result.datetime_utc,
        site=result.site,
        state=state,
        elevation_deg=result.elevation_deg,
        azimuth_deg=result.azimuth_deg,
        angular_radius_deg=ang_radius,
        upper_limb_elevation_deg=upper_limb,
        lower_limb_elevation_deg=lower_limb,
        visible_fraction=visible_fraction,
        range_km=result.range_km,
    )


# ═══════════════════════════════════════════════════════════════════════
# 5.  Public API — single-instant visibility queries
# ═══════════════════════════════════════════════════════════════════════

def sun_visibility(
    site: LandingSite,
    dt_utc: datetime,
) -> VisibilityResult:
    """
    Determine the Sun's geometric visibility from a lunar surface site.

    Returns a VisibilityResult with disk-aware classification.
    """
    result = query_body(SUN_ID, "Sun", site, dt_utc)
    return assess_visibility(result, SUN_RADIUS_KM, SUN_DEFAULT_ANGULAR_RADIUS_DEG)


def earth_visibility(
    site: LandingSite,
    dt_utc: datetime,
) -> VisibilityResult:
    """
    Determine the Earth's geometric visibility from a lunar surface site.

    Returns a VisibilityResult with disk-aware classification.
    """
    result = query_body(EARTH_ID, "Earth", site, dt_utc)
    return assess_visibility(result, EARTH_RADIUS_KM, EARTH_DEFAULT_ANGULAR_RADIUS_DEG)


def full_visibility_report(
    site: LandingSite,
    dt_utc: datetime,
) -> dict:
    """
    Generate a complete visibility report for both Sun and Earth at a
    single instant.

    Returns
    -------
    Dict with 'sun', 'earth', and 'summary' keys.
    """
    sun_vis = sun_visibility(site, dt_utc)
    earth_vis = earth_visibility(site, dt_utc)

    summary = {
        "site_name": site.name,
        "datetime_utc": dt_utc.isoformat(),
        "sun_state": sun_vis.state.value,
        "earth_state": earth_vis.state.value,
        "sun_above_horizon": sun_vis.state in (
            VisibilityState.FULLY_VISIBLE, VisibilityState.PARTIALLY_VISIBLE
        ),
        "earth_above_horizon": earth_vis.state in (
            VisibilityState.FULLY_VISIBLE, VisibilityState.PARTIALLY_VISIBLE
        ),
        "lighting_condition": _describe_lighting(sun_vis, earth_vis),
        "geometric_only_warning": (
            "This report uses geometric visibility only. Terrain "
            "obstructions (craters, ridges) are NOT considered."
        ),
    }

    return {
        "sun": sun_vis.to_dict(),
        "earth": earth_vis.to_dict(),
        "summary": summary,
    }


def _describe_lighting(sun_vis: VisibilityResult, earth_vis: VisibilityResult) -> str:
    """Human-readable description of the lighting/visibility condition."""
    sun_up = sun_vis.state in (
        VisibilityState.FULLY_VISIBLE, VisibilityState.PARTIALLY_VISIBLE
    )
    earth_up = earth_vis.state in (
        VisibilityState.FULLY_VISIBLE, VisibilityState.PARTIALLY_VISIBLE
    )

    if sun_up and earth_up:
        return "Sunlit with Earth visible — ideal for solar power and communication"
    elif sun_up and not earth_up:
        return "Sunlit but Earth below horizon — solar power available, no direct Earth comm"
    elif not sun_up and earth_up:
        return "Lunar night with Earth visible — Earthshine illumination, comm available"
    else:
        return "Lunar night, Earth below horizon — no sunlight, no direct Earth comm"


# ═══════════════════════════════════════════════════════════════════════
# 6.  Time-series visibility
# ═══════════════════════════════════════════════════════════════════════

def visibility_timeline(
    site: LandingSite,
    body_id: str,
    body_name: str,
    body_radius_km: float,
    default_angular_radius_deg: float,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[VisibilityResult]:
    """
    Compute a time series of visibility assessments.

    Parameters
    ----------
    site       : Lunar landing site.
    body_id    : Horizons body ID ("10" or "399").
    body_name  : Human-readable name.
    body_radius_km : Physical radius (km).
    default_angular_radius_deg : Fallback angular radius.
    start_utc  : Start time.
    stop_utc   : End time.
    step_size  : Time step (e.g. "1 h", "30 m").

    Returns
    -------
    List of VisibilityResult, one per time step.
    """
    results = query_body_range(
        body_id, body_name, site, start_utc, stop_utc, step_size
    )
    return [
        assess_visibility(r, body_radius_km, default_angular_radius_deg)
        for r in results
    ]


def sun_visibility_timeline(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[VisibilityResult]:
    """Sun visibility over a time range."""
    return visibility_timeline(
        site, SUN_ID, "Sun", SUN_RADIUS_KM,
        SUN_DEFAULT_ANGULAR_RADIUS_DEG,
        start_utc, stop_utc, step_size,
    )


def earth_visibility_timeline(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[VisibilityResult]:
    """Earth visibility over a time range."""
    return visibility_timeline(
        site, EARTH_ID, "Earth", EARTH_RADIUS_KM,
        EARTH_DEFAULT_ANGULAR_RADIUS_DEG,
        start_utc, stop_utc, step_size,
    )


# ═══════════════════════════════════════════════════════════════════════
# 7.  Horizon-crossing (rise/set) detection
# ═══════════════════════════════════════════════════════════════════════

def find_horizon_crossings(
    site: LandingSite,
    body_id: str,
    body_name: str,
    body_radius_km: float,
    default_angular_radius_deg: float,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[HorizonEvent]:
    """
    Find times when a body's upper limb crosses the geometric horizon.

    A **rise** is when the upper limb transitions from below to above
    the horizon.  A **set** is the reverse.

    The crossing time is estimated by linear interpolation between the
    two adjacent ephemeris steps that straddle the crossing.  Accuracy
    is limited by the step size — use smaller steps for higher precision.

    Parameters
    ----------
    site, body_id, body_name, body_radius_km, default_angular_radius_deg:
        Same as visibility_timeline.
    start_utc, stop_utc : Time range to search.
    step_size           : Time resolution.

    Returns
    -------
    List of HorizonEvent in chronological order.
    """
    results = query_body_range(
        body_id, body_name, site, start_utc, stop_utc, step_size
    )

    if len(results) < 2:
        return []

    events: list[HorizonEvent] = []

    for i in range(len(results) - 1):
        r1 = results[i]
        r2 = results[i + 1]

        if r1.elevation_deg is None or r2.elevation_deg is None:
            continue

        # Compute angular radius for each step
        ar1 = compute_angular_radius(
            body_radius_km, r1.range_km, default_angular_radius_deg
        )
        ar2 = compute_angular_radius(
            body_radius_km, r2.range_km, default_angular_radius_deg
        )

        # Upper limb elevation = center elevation + angular radius
        ul1 = r1.elevation_deg + ar1
        ul2 = r2.elevation_deg + ar2

        # Detect sign change of upper-limb elevation
        if ul1 <= 0 < ul2:
            event_type = "rise"
        elif ul1 > 0 >= ul2:
            event_type = "set"
        else:
            continue

        # Linear interpolation for the crossing time
        dt1 = r1.datetime_utc
        dt2 = r2.datetime_utc
        total_seconds = (dt2 - dt1).total_seconds()

        if abs(ul2 - ul1) > 1e-12:
            frac = -ul1 / (ul2 - ul1)
        else:
            frac = 0.5

        frac = max(0.0, min(1.0, frac))
        crossing_dt = dt1 + timedelta(seconds=frac * total_seconds)

        # Interpolate azimuth
        if r1.azimuth_deg is not None and r2.azimuth_deg is not None:
            # Handle azimuth wraparound
            az1, az2 = r1.azimuth_deg, r2.azimuth_deg
            if abs(az2 - az1) > 180:
                if az2 > az1:
                    az1 += 360
                else:
                    az2 += 360
            crossing_az = (az1 + frac * (az2 - az1)) % 360
        else:
            crossing_az = None

        events.append(HorizonEvent(
            event_type=event_type,
            datetime_utc=crossing_dt,
            body_name=body_name,
            site=site,
            azimuth_deg=round(crossing_az, 4) if crossing_az is not None else None,
        ))

    return events


def find_sun_rise_set(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[HorizonEvent]:
    """Find sunrise and sunset events at a lunar landing site."""
    return find_horizon_crossings(
        site, SUN_ID, "Sun", SUN_RADIUS_KM,
        SUN_DEFAULT_ANGULAR_RADIUS_DEG,
        start_utc, stop_utc, step_size,
    )


def find_earth_rise_set(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[HorizonEvent]:
    """Find Earth-rise and Earth-set events at a lunar landing site."""
    return find_horizon_crossings(
        site, EARTH_ID, "Earth", EARTH_RADIUS_KM,
        EARTH_DEFAULT_ANGULAR_RADIUS_DEG,
        start_utc, stop_utc, step_size,
    )


# ═══════════════════════════════════════════════════════════════════════
# 8.  Sunlit duration estimator
# ═══════════════════════════════════════════════════════════════════════

def estimate_sunlit_hours(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> dict:
    """
    Estimate total hours of sunlight (any part of Sun disk visible)
    over a time range.

    Returns
    -------
    Dict with 'total_hours', 'sunlit_hours', 'dark_hours',
    'sunlit_fraction', and 'partial_hours' (Sun on the horizon).
    """
    results = query_body_range(
        SUN_ID, "Sun", site, start_utc, stop_utc, step_size
    )

    if not results:
        return {
            "total_hours": 0.0,
            "sunlit_hours": 0.0,
            "dark_hours": 0.0,
            "partial_hours": 0.0,
            "sunlit_fraction": 0.0,
        }

    # Parse the step interval from the first two results
    if len(results) >= 2:
        step_hours = (
            (results[1].datetime_utc - results[0].datetime_utc).total_seconds()
            / 3600.0
        )
    else:
        step_hours = 1.0

    sunlit_steps = 0
    partial_steps = 0
    dark_steps = 0

    for r in results:
        vis = assess_visibility(r, SUN_RADIUS_KM, SUN_DEFAULT_ANGULAR_RADIUS_DEG)
        if vis.state == VisibilityState.FULLY_VISIBLE:
            sunlit_steps += 1
        elif vis.state == VisibilityState.PARTIALLY_VISIBLE:
            partial_steps += 1
        else:
            dark_steps += 1

    total_steps = len(results)
    total_hours = total_steps * step_hours
    sunlit_hours = sunlit_steps * step_hours
    partial_hours = partial_steps * step_hours
    dark_hours = dark_steps * step_hours

    return {
        "total_hours": round(total_hours, 2),
        "sunlit_hours": round(sunlit_hours, 2),
        "dark_hours": round(dark_hours, 2),
        "partial_hours": round(partial_hours, 2),
        "sunlit_fraction": (
            round((sunlit_steps + partial_steps) / total_steps, 4)
            if total_steps > 0 else 0.0
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# 9.  Multi-site visibility comparison
# ═══════════════════════════════════════════════════════════════════════

def compare_sites_visibility(
    sites: list[LandingSite],
    dt_utc: datetime,
) -> list[dict]:
    """
    Compare Sun and Earth visibility across multiple landing sites.

    Returns a list of full_visibility_report dicts, one per site.
    """
    comparisons = []
    for site in sites:
        try:
            report = full_visibility_report(site, dt_utc)
            comparisons.append(report)
        except Exception as exc:
            logger.error("Visibility report failed for %s: %s", site.name, exc)
            comparisons.append({
                "summary": {
                    "site_name": site.name,
                    "error": str(exc),
                },
            })
    return comparisons

