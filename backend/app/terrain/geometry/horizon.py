"""Terrain horizon profile by 3D ray casting against the DEM height field (includes Moon curvature).

For an observer O (surface + height) and azimuth a, terrain points are sampled along the great-circle
path at bearing a. Each surface point P(s) = (R + z(s)) * u(s) is converted to an apparent elevation angle
seen from O relative to O's local horizontal plane:  e(s) = atan2((P-O).up, |(P-O)_horizontal|).
A body at elevation el and azimuth a is geometrically blocked iff el <= max_s e(s) (the horizon).
This is the exact visibility test for a point observer against the sampled height field, so no triangle
mesh is needed. Limitations (reported in results): finite tile extent, sampling step growth with distance.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates

from .coordinates import R_REF_M, enu_basis, lonlat_to_vec


def sample_dem(grid, elev, lat, lon):
    r, c = grid.lonlat_to_rowcol(lat, lon)
    return map_coordinates(elev, [np.atleast_1d(r), np.atleast_1d(c)], order=1, mode="constant", cval=np.nan)


def sample_distances(px, max_dist, near=2000.0, growth=1.01):
    d = list(np.arange(px, min(near, max_dist), px))
    s = d[-1] if d else px
    while s < max_dist:
        s = max(s + px, s * growth)
        d.append(s)
    return np.array(d)


def horizon_profile(grid, elev, lat, lon, height_m=0.0, n_az=720, max_dist_m=None, chunk=48):
    """Return dict(azimuth_deg, elevation_deg, distance_m, edge_limited, missing_fraction, observer)."""
    z0 = float(sample_dem(grid, elev, lat, lon)[0])
    if not np.isfinite(z0):
        raise ValueError("Observer is outside the DEM or on a missing pixel")
    px = min(grid.pixel_x, grid.pixel_y)
    h, w = elev.shape
    max_dist = max_dist_m or float(np.hypot(h, w) * px)
    dists = sample_distances(px, max_dist)
    R = grid.R
    east, north, up = enu_basis(lat, lon)
    O = (R + z0 + height_m) * up
    az = np.linspace(0.0, 360.0, n_az, endpoint=False)
    hel = np.full(n_az, -90.0)
    hdist = np.zeros(n_az)
    extent = np.zeros(n_az)
    miss = 0
    tot = 0
    for i in range(0, n_az, chunk):
        a = np.radians(az[i:i + chunk])[:, None, None]
        t = np.cos(a) * north + np.sin(a) * east                    # (A,1,3) tangent at bearing
        th = (dists / R)[None, :, None]
        u = np.cos(th) * up + np.sin(th) * t                        # (A,K,3) unit position vectors
        lat_s = np.degrees(np.arcsin(np.clip(u[..., 2], -1, 1)))
        lon_s = np.degrees(np.arctan2(u[..., 1], u[..., 0]))
        zs = sample_dem(grid, elev, lat_s.ravel(), lon_s.ravel()).reshape(lat_s.shape)
        finite = np.isfinite(zs)
        miss += int((~finite).sum()); tot += finite.size
        P = (R + np.where(finite, zs, 0.0))[..., None] * u
        v = P - O
        upc = v @ up
        hor = np.linalg.norm(v - upc[..., None] * up, axis=-1)
        e = np.degrees(np.arctan2(upc, np.maximum(hor, 1e-9)))
        e = np.where(finite, e, -np.inf)
        k = np.argmax(e, axis=1)
        idx = np.arange(e.shape[0])
        best = e[idx, k]
        sl = slice(i, i + e.shape[0])
        hel[sl] = np.where(np.isfinite(best), best, -90.0)
        hdist[sl] = dists[k]
        last = np.where(finite, dists[None, :], 0.0).max(axis=1)
        extent[sl] = last
    edge_limited = hdist >= 0.8 * np.maximum(extent, 1e-9)
    return {"azimuth_deg": az, "elevation_deg": hel, "distance_m": hdist, "extent_m": extent,
            "edge_limited": edge_limited, "missing_fraction": miss / max(tot, 1),
            "observer": {"lat": float(lat), "lon": float(lon), "ground_elevation_m": z0, "height_m": float(height_m)}}


def interp_horizon(profile, az_deg):
    az = np.asarray(profile["azimuth_deg"])
    el = np.asarray(profile["elevation_deg"])
    return np.interp(np.asarray(az_deg, float) % 360.0, np.append(az, 360.0), np.append(el, el[0]))
