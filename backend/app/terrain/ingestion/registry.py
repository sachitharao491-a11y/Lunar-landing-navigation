"""Registry of NASA PGDA high-resolution LOLA south-pole products (real data sources).

Source page: https://pgda.gsfc.nasa.gov/products/78  (Barker et al., LOLA 5 m/pixel LDEMs)
All rasters: 5 m/pix GeoTIFF, south-polar-stereographic X/Y in metres, MOON_ME frame (DE421).
URL pattern verified against the product page.
"""
from __future__ import annotations

import os

BASE_URL = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp"
PRODUCT_PAGE = "https://pgda.gsfc.nasa.gov/products/78"
LROC_ILLUMINATION = {
    "percent": "https://data.lroc.im-ldi.com/lroc/view_rdr/WAC_POLE_ILL_PCT_SOUTH",
    "time_weighted": "https://data.lroc.im-ldi.com/lroc/view_rdr/WAC_POLE_ILL_TWI_SOUTH",
}
# suffix -> role
PRODUCTS = {"surf": "elevation", "ldec": "count", "slp": "slope", "toterr": "z_uncertainty",
            "slperr": "slope_uncertainty"}

# PGDA key -> description (names per the PGDA page)
SITES = {
    "Site01": "Connecting ridge", "Site04": "Shackleton rim", "Site06": "Nobile rim 1",
    "Site07": "Peak near Shackleton", "Site11": "de Gerlache rim", "Site20": "Leibnitz beta plateau",
    "Site20v2": "Leibnitz beta plateau (extended)", "Site23": "Malapert massif",
    "Site42": "de Gerlache-Kocher massif", "Haworth": "Haworth", "Shoemaker": "Shoemaker",
    "DM1": "Amundsen rim", "DM2": "Nobile rim 2", "SL2": "de Gerlache rim", "SL3": "Connecting ridge extension",
    "NPA": "Cabeus exterior wall 1", "NPB": "Amundsen 1", "NPC": "Idel'son L crater 1",
    "NPD": "Malapert crater 1", "LM1": "Shackleton Rim B", "LM7": "Faustini Rim A",
}
# App database site name -> PGDA key (sites table, see db/002_terrain.sql). Approximate matches.
DB_SITE_TO_PGDA = {
    "Shackleton Crater rim": "Site04", "Connecting Ridge": "Site01", "Haworth Crater rim": "Haworth",
    "Faustini Crater rim": "LM7", "de Gerlache Crater rim": "Site11", "Malapert Massif": "Site23",
    "Cabeus Crater": "NPA", "Nobile Crater rim": "Site06",
}


def filename(key: str, suffix: str) -> str:
    return f"{key}_final_adj_5mpp_{suffix}.tif"


def product_url(key: str, suffix: str) -> str:
    return f"{BASE_URL}/{key}/{filename(key, suffix)}"


def clone_url(key: str, n: int) -> str:
    return f"{BASE_URL}/{key}/Clones/{key}_final_adj_5mpp_{n:04d}_err.tif"


def data_dir(root: str | None = None) -> str:
    return root or os.getenv("TERRAIN_DATA_DIR", "data")


def product_paths(key: str, root: str | None = None) -> dict:
    base = os.path.join(data_dir(root), "raw", key)
    return {role: os.path.join(base, filename(key, s)) for s, role in PRODUCTS.items()}


def availability(key: str, root: str | None = None) -> dict:
    paths = product_paths(key, root)
    have = {role: os.path.exists(p) for role, p in paths.items()}
    return {"key": key, "name": SITES.get(key), "products": have, "elevation_present": have["elevation"],
            "urls": {role: product_url(key, s) for s, role in PRODUCTS.items()}, "paths": paths}
