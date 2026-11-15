"""Interval logic: boolean time series -> intervals with refined transition times."""
from __future__ import annotations

import numpy as np


def build_intervals(t_s, mask, eval_fn=None, refine_s=10.0):
    """Return (intervals, transitions).

    intervals: list of dict(state, start_s, end_s) covering [t_s[0], t_s[-1]]
    transitions: list of dict(time_s, to_state)
    Transitions are refined by bisection with `eval_fn(times)->bool array` (interpolated ephemeris)
    until the bracket is <= refine_s.
    """
    t = np.asarray(t_s, float)
    m = np.asarray(mask, bool)
    idx = np.nonzero(m[1:] != m[:-1])[0]
    cross = np.array([])
    if idx.size:
        lo, hi = t[idx].copy(), t[idx + 1].copy()
        if eval_fn is not None:
            state_lo = m[idx]
            iters = int(np.ceil(np.log2(max((hi - lo).max() / max(refine_s, 1e-3), 1.0))))
            for _ in range(iters):
                mid = 0.5 * (lo + hi)
                same = np.asarray(eval_fn(mid), bool) == state_lo
                lo = np.where(same, mid, lo)
                hi = np.where(same, hi, mid)
        cross = 0.5 * (lo + hi)
    bounds = np.concatenate([[t[0]], cross, [t[-1]]])
    states = [bool(m[0])]
    for _ in cross:
        states.append(not states[-1])
    intervals = [{"state": s, "start_s": float(a), "end_s": float(b)} for s, a, b in zip(states, bounds[:-1], bounds[1:])
                 if b > a]
    transitions = [{"time_s": float(c), "to_state": states[i + 1]} for i, c in enumerate(cross)]
    return intervals, transitions


def summarize(intervals, state, iso):
    sel = [i for i in intervals if i["state"] == state]
    out = [{"start_utc": iso(i["start_s"]), "end_utc": iso(i["end_s"]), "hours": (i["end_s"] - i["start_s"]) / 3600.0} for i in sel]
    total = sum(o["hours"] for o in out)
    longest = max((o["hours"] for o in out), default=0.0)
    return out, total, longest
