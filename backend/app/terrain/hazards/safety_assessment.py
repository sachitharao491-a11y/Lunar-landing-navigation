"""Landing footprint hazard assessment. Statuses: PASS / WARNING / FAIL / UNKNOWN.

Thresholds come from LanderSpec (configurable; defaults are demo values, never universal safe limits).
Precedence: FAIL (a known violation) > UNKNOWN (insufficient data) > WARNING > PASS.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import label, maximum_filter, median_filter, correlate

from ..surface.derivatives import disk_footprint, local_relief, roughness_rms, slope_deg

PASS, WARNING, FAIL, UNKNOWN = "PASS", "WARNING", "FAIL", "UNKNOWN"
_RANK = {PASS: 0, WARNING: 1, UNKNOWN: 2, FAIL: 3}


def combine(statuses):
    return max(statuses, key=lambda s: _RANK[s]) if statuses else UNKNOWN


def _check(name, status, value, limit, units, detail):
    return {"name": name, "status": status, "value": None if value is None else float(value),
            "limit": None if limit is None else float(limit), "units": units, "detail": detail}


def _upper(value, limit, warn_fraction):
    if value > limit:
        return FAIL
    return WARNING if value > warn_fraction * limit else PASS


def terrain_layers(elev, grid, spec, slope_err=None, method="gradient"):
    """Derived layers for a (window of a) DEM."""
    px, py = grid.pixel_x, grid.pixel_y
    scale = grid.scale_grid()
    px_m = min(px, py)
    sl = slope_deg(elev, px, py, scale, method)
    return {"slope": sl, "scale": scale, "px": px_m,
            "rough": roughness_rms(elev, window_px=spec.roughness_window_m / px_m, detrend=True),
            "slope_err": slope_err}


def _masks(shape, rc, spec, px):
    r, c = rc
    rf = spec.footprint_radius_m / px
    rr = (spec.footprint_radius_m + spec.clearance_margin_m) / px
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    d2 = (yy - r) ** 2 + (xx - c) ** 2
    return d2 <= rf ** 2, (d2 <= rr ** 2) & (d2 > rf ** 2)


def evaluate_point(elev, layers, rc, spec, craters=None, count=None, z_err=None):
    """Run all footprint checks at pixel rc=(row, col) of `elev`. Returns dict(status, checks, ...)."""
    px = layers["px"]
    fp, ring = _masks(elev.shape, rc, spec, px)
    if fp.sum() < 3:
        raise ValueError("Footprint smaller than 3 pixels at this resolution; increase footprint_radius_m")
    z, sl, rough = elev, layers["slope"], layers["rough"]
    checks = []
    both = fp | ring

    # data availability
    inv = float((~np.isfinite(z[both])).mean())
    inv_fp = float((~np.isfinite(z[fp])).mean())
    if inv_fp > spec.unknown_if_invalid_fraction:
        st = UNKNOWN
    else:
        st = WARNING if inv > 0 else PASS
    checks.append(_check("missing_data", st, 100 * inv, 100 * spec.unknown_if_invalid_fraction, "% pixels",
                         "Share of footprint+clearance pixels with no elevation value."))

    # 1 max slope
    s_fp = sl[fp]; s_fp = s_fp[np.isfinite(s_fp)]
    if s_fp.size == 0 or inv_fp > spec.unknown_if_invalid_fraction:
        checks.append(_check("max_slope_in_footprint", UNKNOWN, None, spec.max_slope_deg, "deg", "No valid slope data."))
        smax = None
    else:
        smax = float(s_fp.max())
        checks.append(_check("max_slope_in_footprint", _upper(smax, spec.max_slope_deg, spec.warn_fraction), smax,
                             spec.max_slope_deg, "deg", "Largest per-pixel slope inside the landing footprint."))

    # 2 relief across the footprint
    zf = z[fp]; zf = zf[np.isfinite(zf)]
    if zf.size:
        relief = float(zf.max() - zf.min())
        checks.append(_check("elevation_range_in_footprint", _upper(relief, spec.max_relief_m, spec.warn_fraction), relief,
                             spec.max_relief_m, "m", "Max minus min elevation across the footprint."))
    else:
        relief = None
        checks.append(_check("elevation_range_in_footprint", UNKNOWN, None, spec.max_relief_m, "m", "No valid elevations."))

    # 3 roughness (p95 of detrended RMS in footprint)
    rf_ = rough[fp]; rf_ = rf_[np.isfinite(rf_)]
    if rf_.size:
        r95 = float(np.percentile(rf_, 95))
        checks.append(_check("roughness_p95", _upper(r95, spec.max_roughness_m, spec.warn_fraction), r95,
                             spec.max_roughness_m, "m", "95th percentile detrended RMS roughness in the footprint."))
    else:
        r95 = None
        checks.append(_check("roughness_p95", UNKNOWN, None, spec.max_roughness_m, "m", "No valid roughness cells."))

    # 4 craters / depressions
    r0, c0 = rc
    cr_status, worst, near, floor_note = PASS, None, [], None
    if craters is None:
        cr_status = UNKNOWN
    else:
        f, clr = spec.footprint_radius_m, spec.clearance_margin_m
        for cr in craters:
            d = np.hypot(cr["row"] - r0, cr["col"] - c0) * px
            R = cr["radius_m"]
            floor_r, rim_r = 0.6 * R, 1.15 * R          # wall zone = floor edge .. outer rim
            if d + f <= floor_r:                        # footprint entirely on the crater floor
                floor_note = f"Footprint lies on the floor of a {cr['depth_m']:.1f} m deep depression (R~{R:.0f} m); sun/Earth visibility may be reduced."
            elif d + f > floor_r and d - f < rim_r:     # wall or rim crosses the footprint
                near.append(cr)
                cr_status = FAIL if cr["depth_m"] >= spec.crater_fail_depth_m else (cr_status if cr_status == FAIL else WARNING)
            elif d + f + clr > floor_r and d - f - clr < rim_r and cr_status == PASS:
                near.append(cr)
                cr_status = WARNING
        worst = max((c["depth_m"] for c in near), default=None)
    checks.append(_check("crater_depression_proximity", cr_status, worst, spec.crater_fail_depth_m, "m depth",
                         floor_note or "Crater/depression walls or rims crossing the footprint (FAIL if deeper than the limit) or its clearance ring (WARNING)."))

    # 5 obstacles / clearance (5 m DEM cannot resolve boulders; this finds positive terrain features only)
    zz = np.where(np.isfinite(z), z, np.nanmedian(z) if np.isfinite(z).any() else 0.0)
    resid = zz - median_filter(zz, size=max(5, int(round(45.0 / px)) | 1), mode="nearest")
    obs = (resid > spec.obstacle_height_m) & both
    lab, n_obs = label(obs)
    obs_in_fp = int(len(np.unique(lab[obs & fp])))
    obs_status = FAIL if obs_in_fp else (WARNING if n_obs else PASS)
    checks.append(_check("obstacles_clearance", obs_status, n_obs, 0, "count",
                         f"Positive terrain features > {spec.obstacle_height_m} m above local surface; {obs_in_fp} inside footprint."))
    s_ring = sl[ring]; s_ring = s_ring[np.isfinite(s_ring)]
    if s_ring.size:
        rm = float(s_ring.max())
        checks.append(_check("clearance_ring_max_slope", WARNING if rm > spec.max_slope_deg else PASS, rm,
                             spec.max_slope_deg, "deg", "Largest slope in the clearance ring around the footprint (advisory)."))

    # 6 elevation / slope uncertainty
    se = layers.get("slope_err")
    if se is not None and smax is not None:
        hi = np.nanmax((sl + spec.uncertainty_sigma * se)[fp])
        unc_status = WARNING if (hi > spec.max_slope_deg and smax <= spec.max_slope_deg) else PASS
        checks.append(_check("slope_within_uncertainty", unc_status, hi, spec.max_slope_deg, "deg",
                             f"max(slope + {spec.uncertainty_sigma}*slope_uncertainty) in the footprint."))
        unc_area = 100 * float(np.mean((np.nan_to_num(sl + spec.uncertainty_sigma * se, nan=1e9) > spec.max_slope_deg)[both]))
    else:
        checks.append(_check("slope_within_uncertainty", UNKNOWN, None, spec.max_slope_deg, "deg",
                             "No slope-uncertainty layer available."))
        unc_area = None
    status = combine([c["status"] for c in checks])
    return {"footprint_status": status, "checks": checks, "obstacle_count": int(n_obs),
            "uncertain_area_percent": unc_area, "max_slope_deg": smax, "relief_m": relief, "roughness_p95_m": r95,
            "crater_candidates_nearby": near[:5]}


def hazard_map(elev, layers, spec, unknown_frac=None):
    """Per-pixel footprint status map: 0 PASS, 1 WARNING, 2 FAIL, 3 UNKNOWN (max slope + relief + missing data)."""
    px = layers["px"]
    fp = disk_footprint(spec.footprint_radius_m / px)
    sl = np.where(np.isfinite(layers["slope"]), layers["slope"], -np.inf)
    smax = maximum_filter(sl, footprint=fp, mode="nearest")
    rel = local_relief(elev, fp)
    inv = correlate((~np.isfinite(elev)).astype(float), fp / fp.sum(), mode="nearest")
    out = np.zeros(elev.shape, dtype=np.int8)
    out[(smax > spec.warn_fraction * spec.max_slope_deg) | (rel > spec.warn_fraction * spec.max_relief_m)] = 1
    out[(smax > spec.max_slope_deg) | (rel > spec.max_relief_m)] = 2
    out[(inv > spec.unknown_if_invalid_fraction) | ~np.isfinite(smax) | np.isneginf(smax)] = 3
    return out, smax
