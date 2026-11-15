"""Monte Carlo uncertainty propagation through the terrain (and optionally visibility) analysis.

Perturbations are spatially-correlated Gaussian fields scaled by the LOLA total-error layer (TOTERR).
This is a stand-in for NASA's 100 DEM clones (see TERRAIN_ENGINE.md); results are a
"confidence indicator" (share of realizations that PASS), NOT a probability of mission success.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


def perturbation_field(shape, err, corr_px, rng):
    f = gaussian_filter(rng.normal(size=shape), max(0.5, corr_px))
    f /= f.std() + 1e-12
    if err is None:
        return f * 0.0
    e = np.asarray(err, float)
    if e.ndim:
        e = np.where(np.isfinite(e), e, np.nanmedian(e))
    return f * e


def monte_carlo(runs, seed, perturb, evaluate):
    """perturb(rng)->perturbation, evaluate(perturbation)->dict(status, max_slope_deg, [illum, comm])."""
    rng = np.random.default_rng(seed)
    res = [evaluate(perturb(rng)) for _ in range(runs)]
    n = len(res)
    st = {k: sum(r["status"] == k for r in res) for k in ("PASS", "WARNING", "FAIL", "UNKNOWN")}
    pct = lambda key: None if res[0].get(key) is None else [float(np.percentile([r[key] for r in res], q)) for q in (5, 50, 95)]
    out = {"simulation_runs": n, "pass_count": st["PASS"], "status_counts": st,
           "terrain_safety": "PASS" if st["PASS"] == n else ("FAIL" if st["FAIL"] == n else "MIXED"),
           "confidence_indicator_percent": 100.0 * st["PASS"] / n if n else None,
           "max_slope_deg_p5_p50_p95": pct("max_slope_deg"),
           "perturbation_model": "spatially correlated Gaussian field scaled by LOLA TOTERR (not NASA clones)",
           "interpretation": "Share of realizations meeting all configured footprint criteria; not a probability of mission success."}
    for k in ("illumination_percent", "communication_percent"):
        if res[0].get(k) is not None:
            out[k + "_p5_p50_p95"] = pct(k)
    return out
