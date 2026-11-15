"""Terrain derivatives from a projected DEM: slope, aspect, roughness, curvature, local relief."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import correlate, maximum_filter, minimum_filter, uniform_filter


def _ground_scale(px, py, scale):
    """Ground spacing = grid spacing / k. Returns (dx, dy) as scalars or arrays."""
    if scale is None:
        return px, py
    return px / scale, py / scale


def gradients(elev, px, py, scale=None, method="gradient"):
    """Return (dz/dx, dz/dy) in m/m on the ground. +y is grid north (row decreasing)."""
    z = np.asarray(elev, float)
    if method == "horn":
        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], float) / 8.0
        ky = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], float) / 8.0   # +y = up the page
        gx = correlate(z, kx, mode="nearest") / px
        gy = correlate(z, ky, mode="nearest") / py
    elif method == "gradient":
        dz_drow, dz_dcol = np.gradient(z)
        gx, gy = dz_dcol / px, -dz_drow / py
    else:
        raise ValueError("method must be 'gradient' or 'horn'")
    if scale is not None:           # d/dground = k * d/dgrid
        gx, gy = gx * scale, gy * scale
    return gx, gy


def slope_deg(elev, px, py, scale=None, method="gradient"):
    gx, gy = gradients(elev, px, py, scale, method)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def aspect_deg(elev, px, py, scale=None, method="gradient"):
    """Downslope direction, degrees clockwise from GRID north (+y). Flat cells -> NaN.

    Grid north is not true lunar north at the pole; convert before comparing to local azimuths.
    """
    gx, gy = gradients(elev, px, py, scale, method)
    asp = np.degrees(np.arctan2(-gx, -gy)) % 360.0
    return np.where(np.hypot(gx, gy) < 1e-12, np.nan, asp)


def _odd(n):
    n = max(3, int(round(n)))
    return n if n % 2 else n + 1


def roughness_rms(elev, window_px=5, detrend=True):
    """Local RMS of elevation (optionally after removing the best-fit plane) in metres.

    Cells whose window is not fully valid return NaN (never silently zero).
    """
    w = _odd(window_px)
    z = np.asarray(elev, float)
    valid = np.isfinite(z)
    zf = np.where(valid, z, 0.0)
    frac = uniform_filter(valid.astype(float), size=w, mode="nearest")
    full = frac > 0.999
    mean = uniform_filter(zf, size=w, mode="nearest")
    var = uniform_filter(zf ** 2, size=w, mode="nearest") - mean ** 2
    if detrend:
        h = w // 2
        coord = np.arange(-h, h + 1, dtype=float)
        xk = np.tile(coord, (w, 1))
        yk = xk.T
        n = w * w
        mx2 = (w * w - 1) / 12.0
        mxz = correlate(zf, xk, mode="nearest") / n
        myz = correlate(zf, yk, mode="nearest") / n
        var = var - mxz ** 2 / mx2 - myz ** 2 / mx2
    hh = w // 2   # windows overhanging the array edge are incomplete -> NaN (not edge-padded values)
    full[:hh, :] = False; full[-hh:, :] = False; full[:, :hh] = False; full[:, -hh:] = False
    return np.where(full, np.sqrt(np.maximum(var, 0.0)), np.nan)


def curvature(elev, px, py, scale=None):
    """Laplacian of elevation (1/m). Positive = concave (bowl/depression), negative = convex (ridge/peak)."""
    z = np.asarray(elev, float)
    dx, dy = _ground_scale(px, py, scale)
    zxx = (np.roll(z, -1, 1) - 2 * z + np.roll(z, 1, 1)) / dx ** 2
    zyy = (np.roll(z, -1, 0) - 2 * z + np.roll(z, 1, 0)) / dy ** 2
    out = zxx + zyy
    out[0, :] = out[-1, :] = np.nan
    out[:, 0] = out[:, -1] = np.nan
    return out


def disk_footprint(radius_px):
    r = max(0.5, float(radius_px))
    n = int(np.ceil(r))
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    return (xx ** 2 + yy ** 2) <= r ** 2 + 1e-9


def local_relief(elev, footprint):
    """Max - min elevation inside `footprint` (NaN ignored; all-NaN -> NaN)."""
    z = np.asarray(elev, float)
    ok = np.isfinite(z)
    zmax = maximum_filter(np.where(ok, z, -np.inf), footprint=footprint, mode="nearest")
    zmin = minimum_filter(np.where(ok, z, np.inf), footprint=footprint, mode="nearest")
    out = zmax - zmin
    return np.where(np.isfinite(out), out, np.nan)
