"""Local surface normal of the DEM at a point, expressed in the site's East-North-Up basis."""
from __future__ import annotations

import numpy as np

from .coordinates import enu_basis, lonlat_to_vec


def _p(grid, elev, r, c, ref_radius):
    lat, lon = grid.rowcol_to_lonlat(r, c)
    return lonlat_to_vec(lat, lon, ref_radius + elev[r, c])


def surface_normal_enu(grid, elev, row, col, k=1):
    """Unit normal (east, north, up components) from a central-difference of 3D surface points."""
    r, c = int(row), int(col)
    h, w = elev.shape
    k = max(1, int(k))
    if r - k < 0 or c - k < 0 or r + k >= h or c + k >= w:
        raise ValueError("Point too close to the tile edge to estimate a surface normal")
    pts = [elev[r, c + k], elev[r, c - k], elev[r + k, c], elev[r - k, c]]
    if not np.all(np.isfinite(pts)):
        raise ValueError("Missing elevation near the point; surface normal unknown")
    tc = _p(grid, elev, r, c + k, grid.R) - _p(grid, elev, r, c - k, grid.R)
    tr = _p(grid, elev, r + k, c, grid.R) - _p(grid, elev, r - k, c, grid.R)
    n = np.cross(tc, tr)
    lat, lon = grid.rowcol_to_lonlat(r, c)
    east, north, up = enu_basis(float(lat), float(lon))
    if n @ up < 0:
        n = -n
    n = n / np.linalg.norm(n)
    return np.array([n @ east, n @ north, n @ up])
