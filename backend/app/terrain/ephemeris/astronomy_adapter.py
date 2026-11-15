"""Adapter to Member 1's `astronomy` package (JPL Horizons observer ephemeris).

Reuses astronomy.api.horizons_client.query_body_range unchanged; adds time-series fetching, on-disk caching
(Member 1's docs ask for caching to avoid hammering JPL), validation and provenance.
Horizons quantity 4 = airless apparent topocentric azimuth/elevation (light-time and aberration included);
time resolution is one minute.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from .sky import SkyDataError, SkySeries, from_observation_dicts

MAX_ROWS = 20000


class AstronomyUnavailable(RuntimeError):
    pass


def _cache_path(cache_dir, key):
    return os.path.join(cache_dir, hashlib.sha256(key.encode()).hexdigest()[:24] + ".json")


def fetch_sky_series(name, lat_deg, lon_deg_east, altitude_km, start_utc: datetime, end_utc: datetime,
                     step_minutes: int = 10, cache_dir: str | None = None) -> SkySeries:
    """Query Horizons (via Member 1's client) for the Sun and Earth as seen from a lunar surface point."""
    if step_minutes < 1 or int(step_minutes) != step_minutes:
        raise SkyDataError("step_minutes must be a whole number >= 1 (Horizons resolution is one minute)")
    start_utc, end_utc = start_utc.astimezone(timezone.utc), end_utc.astimezone(timezone.utc)
    rows_n = int((end_utc - start_utc).total_seconds() // (60 * step_minutes)) + 1
    if rows_n > MAX_ROWS or rows_n < 2:
        raise SkyDataError(f"Requested {rows_n} samples; allowed range is 2..{MAX_ROWS}. Increase the step or shorten the period.")
    key = f"{lat_deg:.6f}|{lon_deg_east:.6f}|{altitude_km:.5f}|{start_utc:%Y%m%d%H%M}|{end_utc:%Y%m%d%H%M}|{step_minutes}"
    cp = _cache_path(cache_dir, key) if cache_dir else None
    if cp and os.path.exists(cp):
        blob = json.load(open(cp))
        s = from_observation_dicts(blob["rows"], blob["provenance"])
        s.provenance["cache"] = "hit"
        return s
    try:
        from astronomy.api.config import EARTH_ID, SUN_ID
        from astronomy.api.exceptions import AstronomyError
        from astronomy.api.horizons_client import query_body_range
        from astronomy.models.landing_site import LandingSite
    except Exception as e:  # pragma: no cover
        raise AstronomyUnavailable(f"Member 1 astronomy package not importable: {e}") from e
    site = LandingSite(name=name, latitude=lat_deg, longitude=lon_deg_east, altitude_km=altitude_km)
    step = f"{int(step_minutes)} m"
    try:
        sun = query_body_range(SUN_ID, "Sun", site, start_utc, end_utc, step)
        earth = query_body_range(EARTH_ID, "Earth", site, start_utc, end_utc, step)
    except AstronomyError as e:
        raise AstronomyUnavailable(f"JPL Horizons query failed: {e}") from e
    if len(sun) != len(earth):
        raise SkyDataError("Sun and Earth series have different lengths")
    rows = []
    for s, e in zip(sun, earth):
        if s.datetime_utc != e.datetime_utc:
            raise SkyDataError("Sun/Earth timestamps do not match")
        rows.append({"datetime_utc": s.datetime_utc.isoformat(),
                     "sun": {"azimuth_deg": s.azimuth_deg, "elevation_deg": s.elevation_deg, "range_km": s.range_km},
                     "earth": {"azimuth_deg": e.azimuth_deg, "elevation_deg": e.elevation_deg, "range_km": e.range_km}})
    prov = {"source": "JPL Horizons API via Member 1 astronomy module", "fidelity": "jpl_horizons_apparent_airless",
            "quantities": "4 (apparent az/el), 20 (range)", "site": {"name": name, "lat_deg": lat_deg,
                                                                    "lon_deg_east": lon_deg_east, "altitude_km": altitude_km},
            "step_minutes": step_minutes, "fetched_at": datetime.now(timezone.utc).isoformat(), "cache": "miss",
            "limitations": "Apparent (light-time + aberration) directions; Horizons site coordinates are geodetic/planetographic "
                           "while the DEM is planetocentric (identical for a spherical Moon; verify)."}
    if cp:
        os.makedirs(cache_dir, exist_ok=True)
        json.dump({"rows": rows, "provenance": prov}, open(cp, "w"))
    return from_observation_dicts(rows, prov)
