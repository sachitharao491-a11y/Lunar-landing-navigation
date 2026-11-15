"""Data quality control: missing data, measured-vs-interpolated pixels, uncertainty, confidence score."""
from __future__ import annotations

import numpy as np


def _finite_stat(a, fn):
    a = a[np.isfinite(a)]
    return float(fn(a)) if a.size else None


def assess_quality(elev, count=None, z_err=None, slope_err=None, *, ref_sigma_z=1.0, ref_sigma_slope=3.0,
                   target_measured=0.10) -> dict:
    """Transparent data-confidence assessment of an elevation array (tile or window).

    confidence = 100 * valid_fraction * mean(available components), components in [0,1]:
      measured   = clip(measured_fraction / target_measured)    (needs the LDEC count layer)
      z_quality  = clip(1 - median(z_err) / ref_sigma_z)
      slope_qual = clip(1 - median(slope_err) / ref_sigma_slope)
    Reference values are configuration, not NASA standards.
    """
    z = np.asarray(elev, float)
    valid = np.isfinite(z)
    n = z.size
    vf = float(valid.sum()) / n if n else 0.0
    out = {"pixels": int(n), "valid_fraction": vf, "missing_fraction": 1.0 - vf,
           "layers_present": {"count": count is not None, "z_uncertainty": z_err is not None,
                              "slope_uncertainty": slope_err is not None}}
    warnings, comps = [], {}
    if vf < 1.0:
        warnings.append(f"{100 * (1 - vf):.2f}% of elevation pixels are missing (NaN/NoData).")
    if count is not None:
        c = np.asarray(count, float)
        meas = float(((c > 0) & valid).sum()) / max(1, valid.sum())
        out["measured_fraction"], out["interpolated_fraction"] = meas, 1.0 - meas
        comps["measured"] = float(np.clip(meas / target_measured, 0, 1))
        if meas < 0.5:
            warnings.append(f"{100 * (1 - meas):.0f}% of valid pixels are interpolated (LOLA spot count = 0); "
                            "elevation there is not directly measured.")
    else:
        out["measured_fraction"] = out["interpolated_fraction"] = None
        warnings.append("No LOLA count (LDEC) layer: measured vs interpolated pixels cannot be distinguished.")
    if z_err is not None:
        med = _finite_stat(np.asarray(z_err, float), np.median)
        out["z_err_median_m"], out["z_err_p95_m"] = med, _finite_stat(np.asarray(z_err, float), lambda a: np.percentile(a, 95))
        if med is not None:
            comps["z_quality"] = float(np.clip(1 - med / ref_sigma_z, 0, 1))
    else:
        out["z_err_median_m"] = out["z_err_p95_m"] = None
        warnings.append("No elevation-uncertainty layer: uncertainty analysis uses a fallback assumption.")
    if slope_err is not None:
        med = _finite_stat(np.asarray(slope_err, float), np.median)
        out["slope_err_median_deg"] = med
        if med is not None:
            comps["slope_quality"] = float(np.clip(1 - med / ref_sigma_slope, 0, 1))
    else:
        out["slope_err_median_deg"] = None
    out["confidence_components"] = comps
    out["confidence_score"] = float(100.0 * vf * np.mean(list(comps.values()))) if comps else None
    out["data_quality"] = "CHECKED_WITH_WARNINGS" if warnings else "CHECKED"
    out["warnings"] = warnings
    return out
