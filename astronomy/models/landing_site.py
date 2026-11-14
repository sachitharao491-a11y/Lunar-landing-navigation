"""
landing_site.py — Data models for the astronomy module
=======================================================

All shared data structures used across the astronomy package.

Coordinate conventions (enforced at validation time):
    - Longitude : East-positive, −180 to +360 (Horizons accepts both ranges)
    - Latitude  : Selenocentric, −90 to +90
    - Altitude  : Kilometres above reference ellipsoid
    - Azimuth   : 0° North, clockwise through East
    - Elevation : Positive above local geometric horizon
    - Time      : UTC (datetime-aware)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── Landing Site ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LandingSite:
    """
    A location on the lunar surface.

    Attributes:
        name      : Human-readable label (e.g. "Shackleton Rim")
        latitude  : Selenocentric latitude in degrees (−90 to +90)
        longitude : East-positive longitude in degrees (−180 to +360)
        altitude_km : Altitude above the reference ellipsoid in km (default 0)
    """
    name: str
    latitude: float
    longitude: float
    altitude_km: float = 0.0

    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(
                f"Latitude must be between −90° and +90°, got {self.latitude}°"
            )
        if not (-180.0 <= self.longitude <= 360.0):
            raise ValueError(
                f"Longitude must be between −180° and +360°, got {self.longitude}°"
            )
        if not (-10.0 <= self.altitude_km <= 50.0):
            raise ValueError(
                f"Altitude must be between −10 km and +50 km, got {self.altitude_km} km"
            )

    @property
    def site_coord_string(self) -> str:
        """Format for the Horizons SITE_COORD parameter: 'lon,lat,alt'."""
        return f"{self.longitude},{self.latitude},{self.altitude_km}"


# ── Pre-defined Artemis III candidate sites ─────────────────────────────

SHACKLETON_RIM = LandingSite(
    name="Peak Near Shackleton",
    latitude=-89.68,
    longitude=129.0,
)

CONNECTING_RIDGE = LandingSite(
    name="Connecting Ridge",
    latitude=-89.45,
    longitude=-136.0,
)

CONNECTING_RIDGE_EXT = LandingSite(
    name="Connecting Ridge Extension",
    latitude=-89.30,
    longitude=-150.0,
)

DE_GERLACHE_RIM_1 = LandingSite(
    name="de Gerlache Rim 1",
    latitude=-88.50,
    longitude=-68.0,
)

DE_GERLACHE_RIM_2 = LandingSite(
    name="de Gerlache Rim 2",
    latitude=-88.71,
    longitude=-64.0,
)

HAWORTH = LandingSite(
    name="Haworth",
    latitude=-87.45,
    longitude=-5.0,
)

# Convenience list for batch operations
ALL_CANDIDATE_SITES = [
    SHACKLETON_RIM,
    CONNECTING_RIDGE,
    CONNECTING_RIDGE_EXT,
    DE_GERLACHE_RIM_1,
    DE_GERLACHE_RIM_2,
    HAWORTH,
]


# ── Celestial observation result ────────────────────────────────────────

@dataclass
class CelestialResult:
    """
    The observed position of a celestial body from a lunar surface site.

    All angles are in decimal degrees.  Range is in kilometres.
    Fields that Horizons returns as 'n.a.' are stored as None.

    Attributes:
        target_body   : Human-readable name ("Sun", "Earth")
        target_id     : Horizons body ID ("10", "399")
        site          : The observer landing site
        datetime_utc  : Observation time in UTC
        azimuth_deg   : Apparent azimuth (0°=N, clockwise) or None
        elevation_deg : Apparent elevation above local horizon or None
        ra_deg        : Astrometric right ascension (ICRF) or None
        dec_deg       : Astrometric declination (ICRF) or None
        range_km      : Observer-to-target distance in km or None
        range_rate_km_s : Range rate in km/s or None
        illuminated_fraction : Fraction of target disk illuminated (0–1) or None
        phase_angle_deg : Sun-Target-Observer angle in degrees or None
        is_above_horizon : True if elevation_deg > 0, None if elevation unknown
    """
    target_body: str
    target_id: str
    site: LandingSite
    datetime_utc: datetime
    azimuth_deg: Optional[float] = None
    elevation_deg: Optional[float] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    range_km: Optional[float] = None
    range_rate_km_s: Optional[float] = None
    illuminated_fraction: Optional[float] = None
    phase_angle_deg: Optional[float] = None

    @property
    def is_above_horizon(self) -> Optional[bool]:
        """True if the target is geometrically above the local horizon."""
        if self.elevation_deg is None:
            return None
        return self.elevation_deg > 0.0

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "target_body": self.target_body,
            "target_id": self.target_id,
            "site": {
                "name": self.site.name,
                "latitude_deg": self.site.latitude,
                "longitude_deg_east": self.site.longitude,
                "altitude_km": self.site.altitude_km,
            },
            "datetime_utc": self.datetime_utc.isoformat(),
            "azimuth_deg": self.azimuth_deg,
            "elevation_deg": self.elevation_deg,
            "ra_deg": self.ra_deg,
            "dec_deg": self.dec_deg,
            "range_km": self.range_km,
            "range_rate_km_s": self.range_rate_km_s,
            "illuminated_fraction": self.illuminated_fraction,
            "phase_angle_deg": self.phase_angle_deg,
            "is_above_horizon": self.is_above_horizon,
        }


# ── Multi-body observation bundle ───────────────────────────────────────

@dataclass
class SiteObservation:
    """
    Complete Sun + Earth observation from one site at one time.

    Attributes:
        site          : The landing site
        datetime_utc  : Observation time
        sun           : Sun observation result (or None if query failed)
        earth         : Earth observation result (or None if query failed)
    """
    site: LandingSite
    datetime_utc: datetime
    sun: Optional[CelestialResult] = None
    earth: Optional[CelestialResult] = None

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "site": {
                "name": self.site.name,
                "latitude_deg": self.site.latitude,
                "longitude_deg_east": self.site.longitude,
                "altitude_km": self.site.altitude_km,
            },
            "datetime_utc": self.datetime_utc.isoformat(),
            "sun": self.sun.to_dict() if self.sun else None,
            "earth": self.earth.to_dict() if self.earth else None,
        }
