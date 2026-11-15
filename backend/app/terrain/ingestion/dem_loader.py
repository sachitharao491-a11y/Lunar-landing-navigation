"""DEM bundle (elevation + count + uncertainty layers) and GeoTIFF loading.

rasterio and pyproj are imported lazily so the engine and its tests work without them; loading real
GeoTIFFs requires both (see requirements.txt).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from ..geometry.coordinates import R_REF_M, PolarStereoGrid
from . import registry


class DatasetNotAvailable(FileNotFoundError):
    pass


@dataclass
class DEMBundle:
    key: str
    name: str
    elev: np.ndarray
    grid: PolarStereoGrid
    count: Optional[np.ndarray] = None
    z_err: Optional[np.ndarray] = None
    slope_err: Optional[np.ndarray] = None
    nasa_slope: Optional[np.ndarray] = None
    meta: dict = field(default_factory=dict)
    real_data: bool = False

    @property
    def px(self) -> float:
        return min(self.grid.pixel_x, self.grid.pixel_y)

    def window(self, r0, r1, c0, c1) -> "DEMBundle":
        r0, c0 = max(0, int(r0)), max(0, int(c0))
        r1, c1 = min(self.elev.shape[0], int(r1)), min(self.elev.shape[1], int(c1))
        sl = (slice(r0, r1), slice(c0, c1))
        cut = lambda a: None if a is None else a[sl]
        return DEMBundle(self.key, self.name, self.elev[sl], self.grid.subgrid(r0, c0, (r1 - r0, c1 - c0)),
                         cut(self.count), cut(self.z_err), cut(self.slope_err), cut(self.nasa_slope),
                         dict(self.meta), self.real_data)


def _sha256(path: str, cache_dir: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    side = os.path.join(cache_dir, os.path.basename(path) + ".sha256")
    st = os.stat(path)
    tag = f"{st.st_size}:{int(st.st_mtime)}"
    if os.path.exists(side):
        try:
            d = json.load(open(side))
            if d.get("tag") == tag:
                return d["sha256"]
        except Exception:
            pass
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    json.dump({"tag": tag, "sha256": h.hexdigest()}, open(side, "w"))
    return h.hexdigest()


def _grid_from_dataset(ds, assume_radius=R_REF_M) -> tuple[PolarStereoGrid, dict]:
    """Build the grid from the file's CRS (pyproj). Refuse to guess if it is not a polar stereographic."""
    try:
        import pyproj
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pyproj is required to read the CRS of real GeoTIFFs") from e
    crs = pyproj.CRS.from_user_input(ds.crs.to_wkt())
    p = crs.to_dict()
    if p.get("proj") != "stere" or float(p.get("lat_0", 0)) > -89.999:
        raise ValueError(f"Unsupported CRS (expected south polar stereographic): {crs.to_string()[:120]}")
    radius = float(p.get("R") or p.get("a") or assume_radius)
    k0 = float(p.get("k") or p.get("k_0") or 1.0)
    lon0 = float(p.get("lon_0", 0.0))
    t = ds.transform
    grid = PolarStereoGrid((t.a, t.b, t.c, t.d, t.e, t.f), (ds.height, ds.width), radius, k0, lon0)
    return grid, {"crs_proj": {k: p[k] for k in p}, "crs_name": crs.name}


def _read(path, role, expect_shape=None):
    import rasterio
    with rasterio.open(path) as ds:
        arr = ds.read(1).astype("float64")
        nd = ds.nodata
        if nd is not None:
            arr[arr == nd] = np.nan
        arr[~np.isfinite(arr)] = np.nan
        if expect_shape is not None and arr.shape != expect_shape:
            raise ValueError(f"{role} raster shape {arr.shape} != elevation shape {expect_shape}")
        return arr, ds


def load_bundle(key: str, root: str | None = None, reference_radius_m: float = R_REF_M) -> DEMBundle:
    """Load a PGDA LOLA site from disk. Raises DatasetNotAvailable if the elevation file is missing."""
    paths = registry.product_paths(key, root)
    if not os.path.exists(paths["elevation"]):
        raise DatasetNotAvailable(f"{paths['elevation']} not found. Run scripts/download_data.py --site {key}")
    elev, ds = _read(paths["elevation"], "elevation")
    grid, crs_meta = _grid_from_dataset(ds, reference_radius_m)
    meta = {
        "source": "NASA PGDA / LRO LOLA 5 m LDEM", "product_page": registry.PRODUCT_PAGE,
        "site_key": key, "site_name": registry.SITES.get(key), "resolution_m": [grid.pixel_x, grid.pixel_y],
        "coordinate_frame": "MOON_ME (DE421), south polar stereographic X/Y [m]",
        "height_reference": f"metres above sphere R={grid.R:.0f} m (ASSUMPTION - verify in PGDA README)",
        "bounds_xy_m": [float(v) for v in ds.bounds], "shape": list(elev.shape), "nodata": ds.nodata,
        "loaded_at": datetime.now(timezone.utc).isoformat(), "files": {}, **crs_meta,
    }
    cache = os.path.join(registry.data_dir(root), "metadata")
    meta["files"]["elevation"] = {"path": paths["elevation"], "sha256": _sha256(paths["elevation"], cache)}
    layers = {}
    for role in ("count", "z_uncertainty", "slope_uncertainty", "slope"):
        p = paths[role]
        if os.path.exists(p):
            layers[role], _ = _read(p, role, elev.shape)
            meta["files"][role] = {"path": p, "sha256": _sha256(p, cache)}
    return DEMBundle(key, registry.SITES.get(key, key), elev, grid, layers.get("count"), layers.get("z_uncertainty"),
                     layers.get("slope_uncertainty"), layers.get("slope"), meta, real_data=True)
