"""Polar-stereographic grid <-> lunar lon/lat <-> body-fixed 3D (MOON_ME) conversions.

PGDA LOLA 5 m products are south-polar-stereographic X/Y in metres in the MOON_ME frame.
Spherical stereographic with scale k0 at the pole:  rho = 2*R*k0*tan(c/2), c = colatitude from the
south pole, x = rho*sin(lon-lon0), y = rho*cos(lon-lon0).  Parameters are READ FROM THE FILE'S CRS
when available (ingestion.dem_loader); nothing is silently assumed for real data.
"""
from __future__ import annotations

import numpy as np

R_REF_M = 1_737_400.0   # LOLA reference sphere radius (assumption recorded in provenance)


class PolarStereoGrid:
    def __init__(self, transform, shape, radius_m=R_REF_M, k0=1.0, lon0_deg=0.0):
        a, b, c, d, e, f = transform
        if abs(b) > 1e-9 or abs(d) > 1e-9:
            raise ValueError("Rotated rasters are not supported")
        self.a, self.c, self.e, self.f = float(a), float(c), float(e), float(f)
        self.shape, self.R, self.k0, self.lon0 = tuple(shape), float(radius_m), float(k0), float(lon0_deg)

    @property
    def pixel_x(self): return abs(self.a)
    @property
    def pixel_y(self): return abs(self.e)

    def rowcol_to_xy(self, row, col):
        return self.c + self.a * (np.asarray(col) + 0.5), self.f + self.e * (np.asarray(row) + 0.5)

    def xy_to_rowcol(self, x, y):
        return (np.asarray(y) - self.f) / self.e - 0.5, (np.asarray(x) - self.c) / self.a - 0.5

    def xy_to_lonlat(self, x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        cc = 2.0 * np.arctan(np.hypot(x, y) / (2.0 * self.R * self.k0))
        lat = -90.0 + np.degrees(cc)
        lon = (self.lon0 + np.degrees(np.arctan2(x, y)) + 180.0) % 360.0 - 180.0
        return lat, lon

    def lonlat_to_xy(self, lat, lon):
        cc = np.radians(np.asarray(lat, float) + 90.0)
        rho = 2.0 * self.R * self.k0 * np.tan(cc / 2.0)
        dl = np.radians(np.asarray(lon, float) - self.lon0)
        return rho * np.sin(dl), rho * np.cos(dl)

    def rowcol_to_lonlat(self, row, col):
        return self.xy_to_lonlat(*self.rowcol_to_xy(row, col))

    def lonlat_to_rowcol(self, lat, lon):
        return self.xy_to_rowcol(*self.lonlat_to_xy(lat, lon))

    def scale_factor(self, x, y):
        """Point scale factor k = 2*k0/(1+cos c); ground distance = grid distance / k."""
        cc = 2.0 * np.arctan(np.hypot(x, y) / (2.0 * self.R * self.k0))
        return 2.0 * self.k0 / (1.0 + np.cos(cc))

    def scale_grid(self):
        rows, cols = np.mgrid[0:self.shape[0], 0:self.shape[1]]
        return self.scale_factor(*self.rowcol_to_xy(rows, cols))

    def subgrid(self, r0, c0, shape):
        t = (self.a, 0.0, self.c + self.a * c0, 0.0, self.e, self.f + self.e * r0)
        return PolarStereoGrid(t, shape, self.R, self.k0, self.lon0)

    def describe(self) -> dict:
        return {"projection": "south polar stereographic (sphere)", "radius_m": self.R, "k0": self.k0,
                "lon0_deg": self.lon0, "pixel_m": [self.pixel_x, self.pixel_y]}


def lonlat_to_vec(lat_deg, lon_deg, radius=1.0):
    la, lo = np.radians(lat_deg), np.radians(lon_deg)
    return radius * np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)


def vec_to_lonlat(v):
    v = np.asarray(v, float)
    r = np.linalg.norm(v, axis=-1)
    return np.degrees(np.arcsin(v[..., 2] / r)), np.degrees(np.arctan2(v[..., 1], v[..., 0]))


def enu_basis(lat_deg, lon_deg):
    """East, North, Up unit vectors in the body-fixed frame at a point (spherical Moon)."""
    la, lo = np.radians(lat_deg), np.radians(lon_deg)
    east = np.array([-np.sin(lo), np.cos(lo), 0.0])
    north = np.array([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)])
    up = np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
    return east, north, up


def azel_to_enu(az_deg, el_deg):
    """Unit direction(s) in the local East-North-Up basis; azimuth 0=N clockwise (Horizons convention)."""
    az, el = np.radians(np.asarray(az_deg, float)), np.radians(np.asarray(el_deg, float))
    return np.stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)], axis=-1)


def enu_to_azel(v):
    v = np.asarray(v, float)
    return (np.degrees(np.arctan2(v[..., 0], v[..., 1])) % 360.0,
            np.degrees(np.arcsin(np.clip(v[..., 2], -1, 1))))
