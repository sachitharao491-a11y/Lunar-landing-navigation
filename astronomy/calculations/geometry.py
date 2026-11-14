"""
geometry.py — Shared geometry and angle-utility functions
==========================================================

Pure-math helpers used by solar.py, earth_visibility.py, and any
future calculation modules.  **No network calls** — this module
operates entirely on angles and coordinates already retrieved from
Horizons.

Coordinate conventions (consistent with the rest of the package):
    - Azimuth   : 0° = North, clockwise through East (0–360°)
    - Elevation : positive above horizon, negative below (−90° to +90°)
    - Angles    : decimal degrees everywhere unless explicitly noted

All functions accept and return **degrees** unless the docstring
says otherwise.  Internal trigonometry uses radians via NumPy.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np


# ═══════════════════════════════════════════════════════════════════════
# 1.  Angle normalisation
# ═══════════════════════════════════════════════════════════════════════

def normalise_azimuth(az_deg: float) -> float:
    """
    Normalise an azimuth to the range [0, 360).

    Examples:
        normalise_azimuth(-10)  → 350.0
        normalise_azimuth(370)  → 10.0
        normalise_azimuth(0)    → 0.0
    """
    return az_deg % 360.0


def clamp_elevation(el_deg: float) -> float:
    """
    Clamp an elevation to [−90, +90].

    This is a safety net — valid Horizons data should never exceed
    these bounds, but numerical noise could push values slightly out.
    """
    return max(-90.0, min(90.0, el_deg))


# ═══════════════════════════════════════════════════════════════════════
# 2.  Compass direction from azimuth
# ═══════════════════════════════════════════════════════════════════════

# 16-point compass rose
_COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
]


def compass_direction(az_deg: float) -> str:
    """
    Convert an azimuth (degrees) to a 16-point compass label.

    Examples:
        compass_direction(0)    → "N"
        compass_direction(90)   → "E"
        compass_direction(185)  → "S"
        compass_direction(260)  → "W"
    """
    az = normalise_azimuth(az_deg)
    idx = int((az + 11.25) / 22.5) % 16
    return _COMPASS_POINTS[idx]


# ═══════════════════════════════════════════════════════════════════════
# 3.  Angular separation
# ═══════════════════════════════════════════════════════════════════════

def angular_separation(
    az1_deg: float, el1_deg: float,
    az2_deg: float, el2_deg: float,
) -> float:
    """
    Compute the angular separation between two sky positions given in
    azimuth/elevation (horizon coordinates).

    Uses the Vincenty formula for numerical stability at both small
    and large separations.

    Parameters
    ----------
    az1_deg, el1_deg : Azimuth and elevation of position 1 (degrees).
    az2_deg, el2_deg : Azimuth and elevation of position 2 (degrees).

    Returns
    -------
    Angular separation in degrees (0 to 180).
    """
    az1 = np.radians(az1_deg)
    el1 = np.radians(el1_deg)
    az2 = np.radians(az2_deg)
    el2 = np.radians(el2_deg)

    d_az = az2 - az1

    # Vincenty formula
    num = np.sqrt(
        (np.cos(el2) * np.sin(d_az)) ** 2
        + (np.cos(el1) * np.sin(el2)
           - np.sin(el1) * np.cos(el2) * np.cos(d_az)) ** 2
    )
    den = (
        np.sin(el1) * np.sin(el2)
        + np.cos(el1) * np.cos(el2) * np.cos(d_az)
    )

    return float(np.degrees(np.arctan2(num, den)))


# ═══════════════════════════════════════════════════════════════════════
# 4.  Shadow-length estimation
# ═══════════════════════════════════════════════════════════════════════

def shadow_length_ratio(elevation_deg: float) -> Optional[float]:
    """
    Compute the shadow-length multiplier for a given solar elevation.

    For an object of height *h*, the shadow length on flat ground is
    h × shadow_length_ratio.

    Parameters
    ----------
    elevation_deg : Solar elevation above the local horizon (degrees).

    Returns
    -------
    Shadow-length multiplier (dimensionless), or ``None`` if the Sun
    is on or below the horizon (elevation ≤ 0 → infinite / undefined
    shadow).

    Notes
    -----
    - At elevation = 45°, shadow length = object height (ratio = 1.0).
    - At elevation = 90° (zenith), shadow length = 0.
    - This assumes flat terrain and ignores topographic shadowing.
    """
    if elevation_deg <= 0.0:
        return None  # Sun below horizon — no meaningful shadow ratio
    el_rad = math.radians(elevation_deg)
    tan_el = math.tan(el_rad)
    if tan_el <= 0.0:
        return None
    return 1.0 / tan_el


# ═══════════════════════════════════════════════════════════════════════
# 5.  Solar incidence angle on a tilted surface
# ═══════════════════════════════════════════════════════════════════════

def solar_incidence_angle(
    sun_az_deg: float,
    sun_el_deg: float,
    surface_tilt_deg: float = 0.0,
    surface_azimuth_deg: float = 0.0,
) -> float:
    """
    Angle between the incoming sunlight direction and the normal of a
    tilted surface.

    Parameters
    ----------
    sun_az_deg        : Sun azimuth (degrees, 0=N clockwise).
    sun_el_deg        : Sun elevation (degrees above horizon).
    surface_tilt_deg  : Surface tilt from horizontal (0 = flat ground,
                        90 = vertical wall).  Degrees.
    surface_azimuth_deg : Direction the tilted surface faces (degrees,
                          same convention as sun azimuth; 0=N facing).

    Returns
    -------
    Incidence angle in degrees.  0° means sunlight strikes the surface
    head-on (perpendicular); 90° means grazing or parallel.

    Notes
    -----
    For a flat horizontal surface (tilt=0), the incidence angle equals
    90° − sun_el_deg (the zenith angle of the Sun).

    This is useful for estimating solar-panel output or surface heating.
    """
    # Convert to radians
    sun_az  = np.radians(sun_az_deg)
    sun_el  = np.radians(sun_el_deg)
    tilt    = np.radians(surface_tilt_deg)
    surf_az = np.radians(surface_azimuth_deg)

    # Sun direction unit vector (local horizon coordinates)
    #   x = North, y = East, z = Up
    sun_x = np.cos(sun_el) * np.cos(sun_az)
    sun_y = np.cos(sun_el) * np.sin(sun_az)
    sun_z = np.sin(sun_el)

    # Surface normal unit vector
    #   For a surface tilted by 'tilt' degrees from horizontal,
    #   facing azimuth 'surf_az':
    norm_x = np.sin(tilt) * np.cos(surf_az)
    norm_y = np.sin(tilt) * np.sin(surf_az)
    norm_z = np.cos(tilt)

    # Incidence angle = arccos(dot product) — both are unit vectors
    cos_theta = sun_x * norm_x + sun_y * norm_y + sun_z * norm_z
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    return float(np.degrees(np.arccos(cos_theta)))


# ═══════════════════════════════════════════════════════════════════════
# 6.  Elevation-rate estimation (finite difference)
# ═══════════════════════════════════════════════════════════════════════

def elevation_rate_deg_per_hour(
    el_before_deg: float,
    el_after_deg: float,
    dt_hours: float,
) -> float:
    """
    Estimate the rate of change of elevation via finite difference.

    Parameters
    ----------
    el_before_deg : Elevation at the earlier time (degrees).
    el_after_deg  : Elevation at the later time (degrees).
    dt_hours      : Time interval in hours (must be > 0).

    Returns
    -------
    Elevation rate in degrees per hour.  Positive → target is rising.
    """
    if dt_hours <= 0:
        raise ValueError("dt_hours must be positive")
    return (el_after_deg - el_before_deg) / dt_hours

