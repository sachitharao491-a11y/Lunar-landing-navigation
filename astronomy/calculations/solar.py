"""
solar.py — Sun position analysis from a lunar surface site
============================================================

Higher-level functions that combine Horizons API queries with
geometry calculations to provide comprehensive solar analysis.

All functions in this module call the Horizons API (via
horizons_client) and then apply derived calculations using
the geometry module.  They return enriched result dictionaries
that include both raw Horizons data and derived quantities.

Key derived quantities:
    - Compass direction of the Sun
    - Shadow-length ratio
    - Solar incidence angle on a given surface
    - Is the Sun above the geometric horizon?
    - Sun elevation rate (rising / setting)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from astronomy.api.horizons_client import query_sun, query_body_range
from astronomy.api.config import SUN_ID
from astronomy.calculations.geometry import (
    compass_direction,
    normalise_azimuth,
    shadow_length_ratio,
    solar_incidence_angle,
    elevation_rate_deg_per_hour,
)
from astronomy.models.landing_site import CelestialResult, LandingSite

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 1.  Single-instant solar analysis
# ═══════════════════════════════════════════════════════════════════════

def analyse_sun(
    site: LandingSite,
    dt_utc: datetime,
    surface_tilt_deg: float = 0.0,
    surface_azimuth_deg: float = 0.0,
) -> dict:
    """
    Query the Sun's position from a lunar landing site and compute
    derived solar quantities.

    Parameters
    ----------
    site               : Lunar landing site.
    dt_utc             : Observation time (UTC).
    surface_tilt_deg   : Tilt of a surface of interest (for incidence
                         angle); 0 = flat horizontal.
    surface_azimuth_deg: Azimuth direction the surface faces.

    Returns
    -------
    Dictionary with both raw Horizons data and derived quantities::

        {
            "raw": { ... CelestialResult.to_dict() ... },
            "derived": {
                "compass_direction": "W",
                "shadow_length_ratio": 45.8,
                "solar_incidence_angle_deg": 88.75,
                "is_sunlit": false,
                "status": "below_horizon"
            }
        }
    """
    result: CelestialResult = query_sun(site, dt_utc)
    return _enrich_sun_result(result, surface_tilt_deg, surface_azimuth_deg)


def _enrich_sun_result(
    result: CelestialResult,
    surface_tilt_deg: float = 0.0,
    surface_azimuth_deg: float = 0.0,
) -> dict:
    """Add derived quantities to a Sun CelestialResult."""
    derived: dict = {}

    # Compass direction
    if result.azimuth_deg is not None:
        derived["compass_direction"] = compass_direction(result.azimuth_deg)
        derived["azimuth_normalised_deg"] = normalise_azimuth(result.azimuth_deg)
    else:
        derived["compass_direction"] = None
        derived["azimuth_normalised_deg"] = None

    # Shadow length
    if result.elevation_deg is not None:
        derived["shadow_length_ratio"] = shadow_length_ratio(result.elevation_deg)
    else:
        derived["shadow_length_ratio"] = None

    # Solar incidence angle on a surface
    if result.azimuth_deg is not None and result.elevation_deg is not None:
        derived["solar_incidence_angle_deg"] = solar_incidence_angle(
            result.azimuth_deg,
            result.elevation_deg,
            surface_tilt_deg,
            surface_azimuth_deg,
        )
    else:
        derived["solar_incidence_angle_deg"] = None

    # Sunlit status
    if result.elevation_deg is not None:
        # Sun apparent radius ≈ 0.267° as seen from the Moon (same as Earth)
        SUN_APPARENT_RADIUS_DEG = 0.267
        if result.elevation_deg > SUN_APPARENT_RADIUS_DEG:
            derived["is_sunlit"] = True
            derived["status"] = "fully_above_horizon"
        elif result.elevation_deg > -SUN_APPARENT_RADIUS_DEG:
            derived["is_sunlit"] = True  # Partially visible
            derived["status"] = "on_horizon"
        else:
            derived["is_sunlit"] = False
            derived["status"] = "below_horizon"
    else:
        derived["is_sunlit"] = None
        derived["status"] = "unknown"

    return {
        "raw": result.to_dict(),
        "derived": derived,
    }


# ═══════════════════════════════════════════════════════════════════════
# 2.  Multi-datetime solar analysis (comparison across times)
# ═══════════════════════════════════════════════════════════════════════

def analyse_sun_over_time(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[dict]:
    """
    Query the Sun's position from a landing site over a time range
    and compute derived quantities at each step.

    This is the **date/time comparison** function — pass different
    start/stop times to compare solar conditions across periods.

    Parameters
    ----------
    site      : Lunar landing site.
    start_utc : Start of the time range (UTC).
    stop_utc  : End of the time range (UTC).
    step_size : Horizons step size (e.g. "1 h", "30 m", "1 d").

    Returns
    -------
    List of enriched result dicts, one per time step, each containing
    'raw' and 'derived' keys plus an 'elevation_rate_deg_per_hour'
    entry estimated from adjacent steps.
    """
    results = query_body_range(
        SUN_ID, "Sun", site, start_utc, stop_utc, step_size
    )

    enriched = [_enrich_sun_result(r) for r in results]

    # Compute elevation rate between adjacent steps
    for i in range(len(enriched)):
        if i == 0 or i == len(enriched) - 1:
            # Cannot compute rate at boundaries (one-sided)
            if i == 0 and len(enriched) > 1:
                dt_hrs = _hours_between(
                    results[0].datetime_utc, results[1].datetime_utc
                )
                if dt_hrs > 0 and results[0].elevation_deg is not None and results[1].elevation_deg is not None:
                    enriched[i]["derived"]["elevation_rate_deg_per_hour"] = (
                        elevation_rate_deg_per_hour(
                            results[0].elevation_deg,
                            results[1].elevation_deg,
                            dt_hrs,
                        )
                    )
                else:
                    enriched[i]["derived"]["elevation_rate_deg_per_hour"] = None
            else:
                enriched[i]["derived"]["elevation_rate_deg_per_hour"] = None
        else:
            dt_hrs = _hours_between(
                results[i - 1].datetime_utc, results[i + 1].datetime_utc
            )
            if (dt_hrs > 0
                    and results[i - 1].elevation_deg is not None
                    and results[i + 1].elevation_deg is not None):
                enriched[i]["derived"]["elevation_rate_deg_per_hour"] = (
                    elevation_rate_deg_per_hour(
                        results[i - 1].elevation_deg,
                        results[i + 1].elevation_deg,
                        dt_hrs,
                    )
                )
            else:
                enriched[i]["derived"]["elevation_rate_deg_per_hour"] = None

    return enriched


# ═══════════════════════════════════════════════════════════════════════
# 3.  Multi-site comparison at a single time
# ═══════════════════════════════════════════════════════════════════════

def compare_sites_sun(
    sites: list[LandingSite],
    dt_utc: datetime,
) -> list[dict]:
    """
    Compare the Sun's position across multiple landing sites at the
    same UTC instant.

    Returns
    -------
    List of enriched result dicts, one per site, each with a
    "site_name" key for easy identification.
    """
    comparisons = []
    for site in sites:
        try:
            analysis = analyse_sun(site, dt_utc)
            analysis["site_name"] = site.name
            comparisons.append(analysis)
        except Exception as exc:
            logger.error("Sun query failed for site %s: %s", site.name, exc)
            comparisons.append({
                "site_name": site.name,
                "error": str(exc),
            })
    return comparisons


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _hours_between(dt1: datetime, dt2: datetime) -> float:
    """Return the number of hours between two datetimes."""
    return abs((dt2 - dt1).total_seconds()) / 3600.0

