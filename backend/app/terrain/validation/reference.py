"""Comparison of engine outputs with independent NASA reference products."""
from __future__ import annotations

import numpy as np


def compare_arrays(own, ref, border=3, tolerances=(1.0, 2.0)) -> dict:
    a, b = np.asarray(own, float), np.asarray(ref, float)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch {a.shape} vs {b.shape}")
    m = np.isfinite(a) & np.isfinite(b)
    if border:
        m[:border, :] = m[-border:, :] = False
        m[:, :border] = m[:, -border:] = False
    n = int(m.sum())
    if n < 10:
        return {"n_pixels": n, "error": "not enough overlapping valid pixels"}
    d = a[m] - b[m]
    out = {"n_pixels": n, "bias": float(d.mean()), "rmse": float(np.sqrt((d ** 2).mean())), "mae": float(np.abs(d).mean()),
           "p95_abs_diff": float(np.percentile(np.abs(d), 95)),
           "correlation": float(np.corrcoef(a[m], b[m])[0, 1]) if a[m].std() > 0 and b[m].std() > 0 else None}
    for t in tolerances:
        out[f"within_{t:g}_unit_fraction"] = float((np.abs(d) <= t).mean())
    return out


def slope_vs_nasa(own_slope, nasa_slope) -> dict:
    r = compare_arrays(own_slope, nasa_slope)
    r["note"] = ("Own slope uses a 3-point gradient on the 5 m grid; NASA's slope product may use a different baseline or "
                 "smoothing, so differences are expected and are reported, not hidden.")
    return r


def illumination_vs_reference(sim_percent, ref_percent) -> dict:
    """Compare simulated illumination % with an LROC reference % (historical period, different resolution)."""
    if sim_percent is None or ref_percent is None:
        return {"status": "not_available"}
    return {"simulated_percent": float(sim_percent), "reference_percent": float(ref_percent),
            "difference_percent_points": float(sim_percent - ref_percent),
            "caveat": ("LROC WAC illumination maps describe a historical observation period at coarser resolution; they are an "
                       "independent plausibility reference, not a prediction target for another mission date.")}


def sample_lroc_percent(path, lat, lon):
    """Sample an LROC south-pole illumination GeoTIFF at a lunar lon/lat (needs rasterio + pyproj). Untested without data."""
    import pyproj
    import rasterio
    with rasterio.open(path) as ds:
        crs = pyproj.CRS.from_user_input(ds.crs.to_wkt())
        tr = pyproj.Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
        x, y = tr.transform(lon, lat)
        v = next(ds.sample([(x, y)]))[0]
        return None if (ds.nodata is not None and v == ds.nodata) else float(v)
