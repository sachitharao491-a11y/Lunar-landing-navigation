"""SkySeries: time series of Sun and Earth topocentric direction as seen from ONE site.

Convention (Member 1 / JPL Horizons observer quantity 4): azimuth 0=N clockwise, elevation above the local
horizontal plane, airless apparent. Direction vectors are interpolated as unit vectors in the local
East-North-Up basis, so azimuth wrap-around and the pole singularity do not cause artefacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from ..geometry.coordinates import azel_to_enu, enu_to_azel


class SkyDataError(ValueError):
    pass


def _utc(dt) -> datetime:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SkyDataError("Timestamps must be timezone-aware (UTC)")
    return dt.astimezone(timezone.utc)


@dataclass
class SkySeries:
    utc0: datetime
    t_s: np.ndarray
    az: dict          # body -> (T,) degrees
    el: dict
    rng_km: dict
    provenance: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def validate(self):
        t = self.t_s
        if t.size < 2:
            raise SkyDataError("Need at least 2 time samples")
        if np.any(np.diff(t) <= 0):
            raise SkyDataError("Time samples must be strictly increasing")
        for b in ("sun", "earth"):
            for name, arr in (("azimuth", self.az[b]), ("elevation", self.el[b])):
                if arr.shape != t.shape or not np.all(np.isfinite(arr)):
                    raise SkyDataError(f"{b} {name} has missing or non-finite values")
            if np.any(np.abs(self.el[b]) > 90.0):
                raise SkyDataError(f"{b} elevation outside [-90, 90]")
        return self

    @property
    def utc_end(self):
        return self.utc0 + timedelta(seconds=float(self.t_s[-1]))

    def iso(self, t_s) -> str:
        return (self.utc0 + timedelta(seconds=float(t_s))).strftime("%Y-%m-%dT%H:%M:%SZ")

    def interp(self, body, t_query):
        """(az, el, range_km) at arbitrary times by interpolating unit direction vectors."""
        v = azel_to_enu(self.az[body], self.el[body])
        q = np.asarray(t_query, float)
        comp = np.stack([np.interp(q, self.t_s, v[:, i]) for i in range(3)], axis=-1)
        comp /= np.linalg.norm(comp, axis=-1, keepdims=True)
        az, el = enu_to_azel(comp)
        rng = np.interp(q, self.t_s, self.rng_km[body]) if self.rng_km.get(body) is not None else np.full(q.shape, np.nan)
        return az, el, rng

    def summary(self) -> dict:
        return {"start_utc": self.iso(0), "end_utc": self.iso(self.t_s[-1]), "samples": int(self.t_s.size),
                "step_s_median": float(np.median(np.diff(self.t_s))), **self.provenance}


def _body(rows, key):
    az = np.array([np.nan if r[key].get("azimuth_deg") is None else r[key]["azimuth_deg"] for r in rows], float)
    el = np.array([np.nan if r[key].get("elevation_deg") is None else r[key]["elevation_deg"] for r in rows], float)
    rg = np.array([np.nan if r[key].get("range_km") is None else r[key]["range_km"] for r in rows], float)
    return az, el, rg


def from_observation_dicts(rows, provenance=None) -> SkySeries:
    """Build a SkySeries from Member 1's SiteObservation.to_dict() / /v1/observation response items.

    Each row: {"datetime_utc": ISO, "sun": {azimuth_deg, elevation_deg, range_km}, "earth": {...}}
    """
    if not rows:
        raise SkyDataError("No observations supplied")
    rows = sorted(rows, key=lambda r: _utc(r["datetime_utc"]))
    times = [_utc(r["datetime_utc"]) for r in rows]
    t = np.array([(x - times[0]).total_seconds() for x in times], float)
    sa, se, sr = _body(rows, "sun")
    ea, ee, er = _body(rows, "earth")
    s = SkySeries(times[0], t, {"sun": sa, "earth": ea}, {"sun": se, "earth": ee}, {"sun": sr, "earth": er},
                  dict(provenance or {}))
    return s.validate()


def synthetic_sky(start: datetime, hours: float = 24 * 30, step_min: int = 10, sun_el_amp=1.5,
                  sun_period_days=29.53, earth_el_amp=6.0, earth_period_days=27.3, earth_el_offset=0.0) -> SkySeries:
    """TEST/DEMO ONLY: smooth Sun/Earth tracks (NOT an ephemeris). Flagged fidelity='synthetic_test'."""
    t = np.arange(0.0, hours * 3600.0 + 1, step_min * 60.0)
    d = t / 86400.0
    sun_az = (360.0 * d / sun_period_days) % 360.0
    sun_el = sun_el_amp * np.sin(2 * np.pi * d / sun_period_days * 12.37)   # ~ sunrise/set each synodic month
    ea = (180.0 + 7.0 * np.sin(2 * np.pi * d / earth_period_days)) % 360.0
    ee = earth_el_offset + earth_el_amp * np.sin(2 * np.pi * d / earth_period_days + 0.7)
    prov = {"source": "SYNTHETIC_TEST_SKY", "fidelity": "synthetic_test",
            "warning": "Synthetic Sun/Earth tracks for tests/demos only. Not an ephemeris."}
    return SkySeries(_utc(start), t, {"sun": sun_az, "earth": ea}, {"sun": sun_el, "earth": ee},
                     {"sun": np.full(t.shape, 1.496e8), "earth": np.full(t.shape, 384400.0)}, prov,
                     [prov["warning"]]).validate()
