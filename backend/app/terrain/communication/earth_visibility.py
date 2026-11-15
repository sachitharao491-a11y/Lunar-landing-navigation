"""Terrain-aware GEOMETRIC Earth line-of-sight and communication-blackout windows.

Visible <=> Earth centre elevation > max(terrain horizon, antenna elevation mask).
This is line of sight only. It is NOT a link budget: antenna pointing, power, relays and the ground
network are separate considerations.
"""
from __future__ import annotations

import numpy as np

from ..geometry.horizon import interp_horizon
from ..illumination.windows import build_intervals, summarize


def analyze_earth_visibility(sky, horizon, sim) -> dict:
    t = sky.t_s
    az, el = sky.az["earth"], sky.el["earth"]
    h = interp_horizon(horizon, az)
    mask_el = max(0.0, sim.earth_min_elevation_deg)
    thr = np.maximum(h, mask_el)
    vis = el > thr

    def eval_fn(tq):
        a, e, _ = sky.interp("earth", tq)
        return e > np.maximum(interp_horizon(horizon, a), mask_el)

    intervals, trans = build_intervals(t, vis, eval_fn, sim.refine_s)
    win, vis_h, longest_vis = summarize(intervals, True, sky.iso)
    black, black_h, longest_black = summarize(intervals, False, sky.iso)
    dt_h = np.diff(t, append=t[-1]) / 3600.0
    reason = np.where(vis, "visible", np.where(el <= 0.0, "below_local_horizon",
                      np.where(el <= h, "terrain_blocked", "below_antenna_mask")))
    for b in black:            # dominant reason per blackout interval
        i0 = np.searchsorted(t, _to_s(sky, b["start_utc"])); i1 = np.searchsorted(t, _to_s(sky, b["end_utc"]), side="right")
        seg = reason[i0:max(i1, i0 + 1)]
        seg = seg[seg != "visible"]
        b["reason"] = max(set(seg.tolist()), key=seg.tolist().count) if seg.size else "transition"
    span_h = (t[-1] - t[0]) / 3600.0
    return {
        "earth_visible_at_start": bool(vis[0]), "visibility_percent": 100.0 * vis_h / span_h if span_h else None,
        "visibility_hours": vis_h, "blackout_hours": black_h, "simulation_hours": span_h,
        "longest_window_hours": longest_vis, "longest_blackout_hours": longest_black,
        "visibility_windows": win, "blackout_intervals": black,
        "terrain_blocked_hours": float(dt_h[reason == "terrain_blocked"].sum()),
        "below_local_horizon_hours": float(dt_h[reason == "below_local_horizon"].sum()),
        "terrain_obstruction_status": ("PRESENT" if np.any(reason == "terrain_blocked") else "NONE_DETECTED"),
        "transitions": [{"time_utc": sky.iso(x["time_s"]), "event": "acquisition" if x["to_state"] else "loss"} for x in trans],
        "antenna_min_elevation_deg": mask_el, "earth_elevation_range_deg": [float(el.min()), float(el.max())],
        "scope": "geometric line of sight only; not a radio link budget", "refine_tolerance_s": sim.refine_s,
    }


def _to_s(sky, iso):
    from datetime import datetime
    return (datetime.fromisoformat(iso.replace("Z", "+00:00")) - sky.utc0).total_seconds()
