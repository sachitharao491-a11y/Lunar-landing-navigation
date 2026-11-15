"""Terrain-aware sunlight simulation.

Directly lit  <=>  (visible fraction of the Sun's disk above the terrain horizon > min_lit_fraction)
                   AND (n . s > 0, local surface normal faces the Sun).
Reuses Member 1's disk geometry (compute_visible_fraction, compute_angular_radius) unchanged.
"""
from __future__ import annotations

import numpy as np

from astronomy.calculations.visibility import (SUN_DEFAULT_ANGULAR_RADIUS_DEG, SUN_RADIUS_KM,
                                               compute_angular_radius, compute_visible_fraction)

from ..geometry.coordinates import azel_to_enu
from ..geometry.horizon import interp_horizon
from .windows import build_intervals, summarize


def _fractions(el, az, rng, horizon):
    h = interp_horizon(horizon, az)
    ang = np.array([compute_angular_radius(SUN_RADIUS_KM, None if not np.isfinite(r) else r, SUN_DEFAULT_ANGULAR_RADIUS_DEG)
                    for r in np.atleast_1d(rng)])
    frac = np.array([compute_visible_fraction(float(e - hh), float(a)) for e, hh, a in zip(np.atleast_1d(el), np.atleast_1d(h), ang)])
    return frac, h, ang


def analyze_illumination(sky, horizon, normal_enu, sim) -> dict:
    t = sky.t_s
    az, el, rng = sky.az["sun"], sky.el["sun"], sky.rng_km["sun"]
    frac, h, ang = _fractions(el, az, rng, horizon)
    n = np.asarray(normal_enu, float)
    inc = azel_to_enu(az, el) @ n > 0
    lit = (frac > sim.min_lit_fraction) & inc
    geom_up = (el + ang) > 0.0

    def eval_fn(tq):
        a, e, r = sky.interp("sun", tq)
        f, _, _ = _fractions(e, a, r, horizon)
        return (f > sim.min_lit_fraction) & (azel_to_enu(a, e) @ n > 0)

    intervals, trans = build_intervals(t, lit, eval_fn, sim.refine_s)
    sun_iv, lit_h, longest_lit = summarize(intervals, True, sky.iso)
    dark_iv, dark_h, longest_dark = summarize(intervals, False, sky.iso)
    span_h = (t[-1] - t[0]) / 3600.0
    dt_h = np.diff(t, append=t[-1]) / 3600.0       # last sample has zero weight (end instant)
    blocked_h = float(dt_h[geom_up & (frac <= sim.min_lit_fraction)].sum())
    incid_h = float(dt_h[(frac > sim.min_lit_fraction) & ~inc].sum())
    return {
        "percent_illuminated": 100.0 * lit_h / span_h if span_h else None,
        "mean_visible_disk_percent": float(100.0 * (frac * dt_h).sum() / max(dt_h.sum(), 1e-9)),
        "sunlight_hours": lit_h, "darkness_hours": dark_h, "simulation_hours": span_h,
        "longest_sunlight_hours": longest_lit, "longest_darkness_hours": longest_dark,
        "sunlight_intervals": sun_iv, "darkness_intervals": dark_iv,
        "transitions": [{"time_utc": sky.iso(x["time_s"]), "event": "sunrise" if x["to_state"] else "sunset"} for x in trans],
        "terrain_blocked_hours": blocked_h, "incidence_limited_hours": incid_h,
        "sun_elevation_range_deg": [float(el.min()), float(el.max())],
        "time_step_minutes": float(np.median(np.diff(t)) / 60.0), "refine_tolerance_s": sim.refine_s,
        "definition": "lit = Sun disk (any part) above the terrain horizon AND surface normal faces the Sun",
    }
