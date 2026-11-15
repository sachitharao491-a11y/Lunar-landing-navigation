"""Multi-scale crater / depression candidate detection with verification against elevation and slope.

Method (a circular Hough transform alone cannot handle irregular or overlapping craters):
 1. For radius r, split the rim annulus (r..1.5r) into 8 angular sectors and compute each sector's mean.
 2. enclosed_depth = (2nd-lowest valid sector mean) - (mean of the interior disk). At least seven rim
    sectors must have adequate data; missing sectors are not treated as high ground.
    3. Keep spatial local maxima with enclosed_depth >= min_depth_m and depth/diameter >= min_depth_ratio,
       then suppress duplicates across scales. Mean wall slope is reported for downstream review; it is not
       currently a candidate acceptance threshold.
Output items are CANDIDATES; depth and wall slope are reported so downstream checks decide.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.signal import fftconvolve


def _grid_xy(r):
    n = int(np.ceil(r))
    return np.mgrid[-n:n + 1, -n:n + 1]


def _disk(r):
    yy, xx = _grid_xy(r)
    return (xx ** 2 + yy ** 2) <= r ** 2


def _sector_rings(r0, r1, sectors=8):
    yy, xx = _grid_xy(r1)
    d2 = xx ** 2 + yy ** 2
    ring = (d2 > r0 ** 2) & (d2 <= r1 ** 2)
    sec = ((np.arctan2(yy, xx) + np.pi) / (2 * np.pi) * sectors).astype(int) % sectors
    return [ring & (sec == k) for k in range(sectors)], ring


def _masked_mean(z, valid, kernel):
    k = kernel.astype(float)
    num = fftconvolve(np.where(valid, z, 0.0), k, mode="same")
    den = fftconvolve(valid.astype(float), k, mode="same")
    ok = den > 0.5 * k.sum()
    return np.where(ok, num / np.maximum(den, 1e-9), np.nan)


def detect_craters(elev, px, slope=None, grid=None, radii_m=(15, 30, 60, 120, 240), min_depth_m=1.0,
                   min_depth_ratio=0.02, max_candidates=100):
    z = np.asarray(elev, float)
    if z.ndim != 2:
        raise ValueError("elev must be a 2D array")
    if not np.isfinite(px) or px <= 0:
        raise ValueError("px must be a finite positive pixel size")
    if max_candidates <= 0:
        return []
    valid = np.isfinite(z)
    found = []
    for rm in radii_m:
        r = rm / px
        if r < 2.5 or 3.2 * r > min(z.shape):
            continue
        inner = _masked_mean(z, valid, _disk(r))
        sectors, _ = _sector_rings(r, 1.5 * r)
        stack = np.stack([_masked_mean(z, valid, s) for s in sectors])           # (8,H,W)
        valid_sectors = np.isfinite(stack)
        with np.errstate(invalid="ignore"):
            # Sort absent sectors after real measurements, then reject centres with
            # fewer than seven valid sectors instead of reading missing data as rim.
            ordered = np.partition(np.where(valid_sectors, stack, np.inf), 1, axis=0)
            depth = ordered[1] - inner                                            # 2nd-lowest valid sector
        enough_rim = valid_sectors.sum(axis=0) >= 7
        depth = np.where(enough_rim & np.isfinite(inner) & np.isfinite(depth), depth, -np.inf)
        enclosed = ((stack - inner[None, :, :]) >= 0.5 * depth[None, :, :]).sum(axis=0) / len(stack)
        size = int(2 * r + 1)
        peaks = ((depth == maximum_filter(depth, size=size)) & (depth >= min_depth_m)
                 & (depth / (2 * rm) >= min_depth_ratio) & (enclosed >= 7 / 8))
        yy, xx = _grid_xy(r)
        wall = ((xx ** 2 + yy ** 2) <= r ** 2) & ((xx ** 2 + yy ** 2) > (0.6 * r) ** 2)
        h = wall.shape[0] // 2
        for rr, cc in zip(*np.nonzero(peaks)):
            ws = None
            if slope is not None and rr - h >= 0 and cc - h >= 0 and rr + h < z.shape[0] and cc + h < z.shape[1]:
                vals = slope[rr - h:rr + h + 1, cc - h:cc + h + 1][wall]
                vals = vals[np.isfinite(vals)]
                ws = float(vals.mean()) if vals.size else None
            encl = float(enclosed[rr, cc])
            item = {"row": int(rr), "col": int(cc), "radius_m": float(rm), "depth_m": float(depth[rr, cc]),
                    "depth_diameter_ratio": float(depth[rr, cc] / (2 * rm)), "wall_slope_deg": ws,
                    "enclosure_fraction": encl}
            if grid is not None:
                lat, lon = grid.rowcol_to_lonlat(rr, cc)
                item["lat"], item["lon"] = float(lat), float(lon)
            found.append(item)
    found.sort(key=lambda d: -d["depth_m"])
    kept = []
    for c in found:   # non-maximum suppression across scales
        if all(np.hypot(c["row"] - k["row"], c["col"] - k["col"]) * px > 0.8 * max(c["radius_m"], k["radius_m"]) for k in kept):
            kept.append(c)
        if len(kept) >= max_candidates:
            break
    return kept
