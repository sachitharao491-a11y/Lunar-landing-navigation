"""Deterministic SYNTHETIC south-pole terrain for tests and offline demos.

This is NOT lunar data. Bundles are flagged real_data=False and every API response carries that flag.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from ..geometry.coordinates import R_REF_M, PolarStereoGrid
from .dem_loader import DEMBundle


def fractal(shape, rng, amplitude_m=4.0, h=0.9, sigmas=(2, 4, 8, 16, 32, 64)):
    out = np.zeros(shape)
    for s in sigmas:
        f = gaussian_filter(rng.normal(size=shape), s)
        f /= f.std() + 1e-12
        out += f * (s ** h)
    return out / out.std() * amplitude_m


def add_crater(z, r0, c0, radius_px, depth_m, rim_m=0.0):
    rr, cc = np.mgrid[0:z.shape[0], 0:z.shape[1]]
    d = np.hypot(rr - r0, cc - c0) / radius_px
    bowl = -depth_m * np.clip(1 - d ** 2, 0, None)
    rim = rim_m * np.exp(-((d - 1.0) / 0.15) ** 2)
    return z + bowl + rim


def make_synthetic_bundle(size=500, pixel_m=5.0, lat=-89.6, lon=30.0, seed=7, roughness_m=1.6,
                          craters=True, ridge=True) -> DEMBundle:
    rng = np.random.default_rng(seed)
    z = 800.0 + fractal((size, size), rng, roughness_m)
    if craters:
        z = add_crater(z, size * 0.80, size * 0.66, 28, 9.0, 1.5)
        z = add_crater(z, size * 0.60, size * 0.22, 14, 5.0, 0.5)
    if ridge:   # a 40 m high ridge 600 m from the tile centre, running east-west
        rr = np.arange(size)[:, None]
        z = z + 40.0 * np.exp(-(((rr - size * 0.5) + 120) / 12.0) ** 2) * np.ones((1, size))
    g0 = PolarStereoGrid((pixel_m, 0, 0, 0, -pixel_m, 0), (size, size))
    cx, cy = g0.lonlat_to_xy(lat, lon)
    left, top = float(cx) - size * pixel_m / 2, float(cy) + size * pixel_m / 2
    grid = PolarStereoGrid((pixel_m, 0, left, 0, -pixel_m, top), (size, size))
    count = (rng.random((size, size)) < 0.08).astype(float)
    z_err = np.full((size, size), 0.4) * (1 + 0.3 * gaussian_filter(rng.normal(size=(size, size)), 20))
    s_err = np.full((size, size), 2.0)
    meta = {"source": "SYNTHETIC_DEMO", "site_key": "SYNTHETIC", "site_name": "Synthetic demo terrain",
            "resolution_m": [pixel_m, pixel_m], "coordinate_frame": "MOON_ME (synthetic)",
            "height_reference": f"metres above sphere R={R_REF_M:.0f} m (synthetic)", "shape": [size, size],
            "files": {}, "warning": "SYNTHETIC terrain generated for tests/demo. Not lunar data."}
    return DEMBundle("SYNTHETIC", "Synthetic demo terrain", z, grid, count, z_err, s_err, None, meta, real_data=False)
