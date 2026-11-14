"""
earth_visibility.py — Earth position and visibility analysis
==============================================================

Higher-level functions for analysing Earth's visibility and position
from a lunar surface site.  Earth visibility is critical for:

    - Communication windows (direct-to-Earth radio links)
    - Earth observation from the lunar surface
    - Navigation reference (Earth as a visual landmark)

At the lunar south pole, Earth's elevation oscillates between
roughly +6° and −6° over a ~27.3-day cycle due to lunar libration.
Whether Earth is visible at a given instant depends on the observer's
exact selenographic coordinates and the current libration state.

Key derived quantities:
    - Compass direction of Earth
    - Communication feasibility (elevation above minimum threshold)
    - Earth phase description (full, gibbous, quarter, crescent, new)
    - Angular separation between Sun and Earth
    - Earth elevation trend (rising / setting)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from astronomy.api.horizons_client import query_earth, query_body_range
from astronomy.api.config import EARTH_ID
from astronomy.calculations.geometry import (
    angular_separation,
    compass_direction,
    normalise_azimuth,
    elevation_rate_deg_per_hour,
)
from astronomy.models.landing_site import CelestialResult, LandingSite

logger = logging.getLogger(__name__)

# Minimum elevation above horizon for reliable communication (degrees).
# This is a rough engineering threshold — actual values depend on
# antenna design and link budget.  A more conservative threshold would
# be 5°.  We use 1° as a geometric minimum.
MIN_COMM_ELEVATION_DEG = 1.0


# ═══════════════════════════════════════════════════════════════════════
# 1.  Single-instant Earth analysis
# ═══════════════════════════════════════════════════════════════════════

def analyse_earth(
    site: LandingSite,
    dt_utc: datetime,
    sun_azimuth_deg: Optional[float] = None,
    sun_elevation_deg: Optional[float] = None,
) -> dict:
    """
    Query Earth's position from a lunar landing site and compute
    derived quantities.

    Parameters
    ----------
    site              : Lunar landing site.
    dt_utc            : Observation time (UTC).
    sun_azimuth_deg   : (Optional) Sun azimuth at the same time — if
                        provided, angular separation is computed.
    sun_elevation_deg : (Optional) Sun elevation at the same time.

    Returns
    -------
    Dictionary with raw Horizons data and derived quantities::

        {
            "raw": { ... },
            "derived": {
                "compass_direction": "SW",
                "earth_phase_name": "crescent",
                "is_earth_visible": true,
                "communication_feasible": true,
                "sun_earth_angular_separation_deg": 24.8
            }
        }
    """
    result: CelestialResult = query_earth(site, dt_utc)
    return _enrich_earth_result(
        result, sun_azimuth_deg, sun_elevation_deg
    )


def _enrich_earth_result(
    result: CelestialResult,
    sun_azimuth_deg: Optional[float] = None,
    sun_elevation_deg: Optional[float] = None,
) -> dict:
    """Add derived quantities to an Earth CelestialResult."""
    derived: dict = {}

    # Compass direction
    if result.azimuth_deg is not None:
        derived["compass_direction"] = compass_direction(result.azimuth_deg)
        derived["azimuth_normalised_deg"] = normalise_azimuth(result.azimuth_deg)
    else:
        derived["compass_direction"] = None
        derived["azimuth_normalised_deg"] = None

    # Earth visibility (geometric)
    if result.elevation_deg is not None:
        derived["is_earth_visible"] = result.elevation_deg > 0.0
        derived["communication_feasible"] = (
            result.elevation_deg >= MIN_COMM_ELEVATION_DEG
        )
        derived["comm_elevation_margin_deg"] = (
            result.elevation_deg - MIN_COMM_ELEVATION_DEG
        )
    else:
        derived["is_earth_visible"] = None
        derived["communication_feasible"] = None
        derived["comm_elevation_margin_deg"] = None

    # Earth phase name from illuminated fraction
    if result.illuminated_fraction is not None:
        derived["earth_phase_name"] = _phase_name(result.illuminated_fraction)
        derived["earth_phase_percent"] = round(
            result.illuminated_fraction * 100, 2
        )
    else:
        derived["earth_phase_name"] = None
        derived["earth_phase_percent"] = None

    # Angular separation from Sun (if Sun data provided)
    if (sun_azimuth_deg is not None and sun_elevation_deg is not None
            and result.azimuth_deg is not None
            and result.elevation_deg is not None):
        derived["sun_earth_angular_separation_deg"] = angular_separation(
            sun_azimuth_deg, sun_elevation_deg,
            result.azimuth_deg, result.elevation_deg,
        )
    else:
        derived["sun_earth_angular_separation_deg"] = None

    return {
        "raw": result.to_dict(),
        "derived": derived,
    }


# ═══════════════════════════════════════════════════════════════════════
# 2.  Multi-datetime Earth analysis (comparison across times)
# ═══════════════════════════════════════════════════════════════════════

def analyse_earth_over_time(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> list[dict]:
    """
    Query Earth's position from a landing site over a time range and
    compute derived quantities at each step.

    Use this to find **communication windows** — periods when Earth
    is above the horizon and above the minimum communication elevation.

    Parameters
    ----------
    site      : Lunar landing site.
    start_utc : Start of the time range (UTC).
    stop_utc  : End of the time range (UTC).
    step_size : Horizons step size (e.g. "1 h", "6 h", "1 d").

    Returns
    -------
    List of enriched result dicts, one per time step.
    """
    results = query_body_range(
        EARTH_ID, "Earth", site, start_utc, stop_utc, step_size
    )

    enriched = [_enrich_earth_result(r) for r in results]

    # Compute elevation rate between adjacent steps
    for i in range(len(enriched)):
        if i == 0 or i == len(enriched) - 1:
            if i == 0 and len(enriched) > 1:
                dt_hrs = _hours_between(
                    results[0].datetime_utc, results[1].datetime_utc
                )
                if (dt_hrs > 0
                        and results[0].elevation_deg is not None
                        and results[1].elevation_deg is not None):
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
# 3.  Communication window finder
# ═══════════════════════════════════════════════════════════════════════

def find_communication_windows(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
    min_elevation_deg: float = MIN_COMM_ELEVATION_DEG,
) -> list[dict]:
    """
    Find time windows when Earth is above a minimum elevation,
    suitable for direct-to-Earth communication.

    Returns a list of window dicts, each with 'start', 'end', and
    'duration_hours'.  Resolution is limited by step_size.

    Parameters
    ----------
    site              : Lunar landing site.
    start_utc, stop_utc : Time range to search.
    step_size         : Time resolution (default "1 h").
    min_elevation_deg : Minimum Earth elevation for communication.

    Returns
    -------
    List of dicts::

        [
            {
                "start": "2026-03-01T06:00:00+00:00",
                "end":   "2026-03-14T18:00:00+00:00",
                "duration_hours": 324.0,
                "max_elevation_deg": 5.8
            },
            ...
        ]
    """
    results = query_body_range(
        EARTH_ID, "Earth", site, start_utc, stop_utc, step_size
    )

    windows: list[dict] = []
    in_window = False
    window_start: datetime | None = None
    max_el: float = 0.0

    for r in results:
        if r.elevation_deg is not None and r.elevation_deg >= min_elevation_deg:
            if not in_window:
                in_window = True
                window_start = r.datetime_utc
                max_el = r.elevation_deg
            else:
                max_el = max(max_el, r.elevation_deg)
        else:
            if in_window:
                windows.append({
                    "start": window_start.isoformat() if window_start else None,
                    "end": r.datetime_utc.isoformat(),
                    "duration_hours": round(
                        _hours_between(window_start, r.datetime_utc), 2
                    ) if window_start else None,
                    "max_elevation_deg": round(max_el, 4),
                })
                in_window = False

    # Handle case where the time range ends while still in a window
    if in_window and results:
        windows.append({
            "start": window_start.isoformat() if window_start else None,
            "end": results[-1].datetime_utc.isoformat(),
            "duration_hours": round(
                _hours_between(window_start, results[-1].datetime_utc), 2
            ) if window_start else None,
            "max_elevation_deg": round(max_el, 4),
        })

    return windows


# ═══════════════════════════════════════════════════════════════════════
# 4.  Multi-site comparison at a single time
# ═══════════════════════════════════════════════════════════════════════

def compare_sites_earth(
    sites: list[LandingSite],
    dt_utc: datetime,
) -> list[dict]:
    """
    Compare Earth's visibility across multiple landing sites at the
    same UTC instant.

    Returns a list of enriched dicts, one per site.
    """
    comparisons = []
    for site in sites:
        try:
            analysis = analyse_earth(site, dt_utc)
            analysis["site_name"] = site.name
            comparisons.append(analysis)
        except Exception as exc:
            logger.error("Earth query failed for site %s: %s", site.name, exc)
            comparisons.append({
                "site_name": site.name,
                "error": str(exc),
            })
    return comparisons


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _phase_name(illuminated_fraction: float) -> str:
    """
    Map an illuminated fraction (0–1) to a human-readable phase name.

    These thresholds are approximate and for display purposes only.
    """
    pct = illuminated_fraction * 100
    if pct < 1.0:
        return "new"
    elif pct < 25.0:
        return "crescent"
    elif pct < 40.0:
        return "quarter"
    elif pct < 60.0:
        return "gibbous"
    elif pct < 75.0:
        return "gibbous"
    elif pct < 99.0:
        return "nearly full"
    else:
        return "full"


def _hours_between(dt1: datetime, dt2: datetime) -> float:
    """Return the number of hours between two datetimes."""
    return abs((dt2 - dt1).total_seconds()) / 3600.0

