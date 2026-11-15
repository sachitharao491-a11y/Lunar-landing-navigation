"""REST API for the terrain & mission analysis engine (Member 2), mounted by app.main.

Data flow:  PGDA LOLA GeoTIFFs (or labeled synthetic fallback)  +  Member 1 Sun/Earth series  ->  engine  ->  JSON
Heavy computation runs in a worker thread, limited by a semaphore, with a timeout.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import struct
import zlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .terrain.config import ALGORITHM_VERSION, AnalysisConfig, config_from_dict
from .terrain.ephemeris.astronomy_adapter import AstronomyUnavailable, fetch_sky_series
from .terrain.ephemeris.sky import SkyDataError, from_observation_dicts, synthetic_sky
from .terrain.ingestion import registry
from .terrain.ingestion.dem_loader import DatasetNotAvailable, load_bundle
from .terrain.ingestion.synthetic import make_synthetic_bundle
from .terrain.pipeline import clean, run_analysis
from .terrain.scoring.site_ranking import rank_sites

log = logging.getLogger("lunar.terrain")
router = APIRouter(prefix="/api/analysis", tags=["terrain-analysis"])

DATA_DIR = registry.data_dir()
CACHE_DIR = os.path.join(DATA_DIR, "cache", "horizons")
TIMEOUT_S = float(os.getenv("ANALYSIS_TIMEOUT_S", "300"))
_sem = asyncio.Semaphore(int(os.getenv("ANALYSIS_CONCURRENCY", "2")))
_bundles: dict = {}

LOLA_HILLSHADE_COG = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ_HILL.TIF"
LOLA_HILLSHADE_PRODUCT = "LDEM_80S_20MPP_ADJ_HILL.TIF"


def _png_grayscale(pixels) -> bytes:
    """Encode an 8-bit grayscale preview without adding a backend image dependency."""
    import numpy as np

    values = np.asarray(pixels, dtype=np.float64)
    valid = np.isfinite(values)
    if not valid.any():
        raise HTTPException(422, "The requested LOLA window contains no valid hillshade pixels.")
    finite = values[valid]
    low, high = float(finite.min()), float(finite.max())
    if high > low:
        display = np.clip((values - low) * (255.0 / (high - low)), 0, 255)
    else:
        display = np.zeros_like(values)
    display[~valid] = 0
    gray = display.astype(np.uint8)
    height, width = gray.shape
    scanlines = b"".join(b"\0" + gray[row].tobytes() for row in range(height))

    def chunk(kind: bytes, content: bytes) -> bytes:
        body = kind + content
        return struct.pack(">I", len(content)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(scanlines, 6)) + chunk(b"IEND", b"")


@router.get("/lola/preview", tags=["terrain-analysis"], summary="Preview a coordinate window from the NASA LOLA south-pole hillshade")
def lola_preview(
    latitude_deg: float = Query(..., ge=-90, le=-80),
    longitude_deg_east: float = Query(..., ge=-180, le=360),
    radius_km: float = Query(3.0, gt=0, le=20),
):
    """Read only a small coordinate-centered window from NASA's public cloud-optimized GeoTIFF."""
    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.windows import Window
        from .terrain.geometry.coordinates import PolarStereoGrid

        raster_path = f"/vsicurl/{LOLA_HILLSHADE_COG}"
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".TIF",
            GDAL_HTTP_TIMEOUT="30",
            GDAL_HTTP_CONNECTTIMEOUT="15",
            GDAL_HTTP_MULTIRANGE="YES",
        ):
            with rasterio.open(raster_path) as dataset:
                if dataset.crs is None:
                    raise HTTPException(502, "The LOLA hillshade product did not include its coordinate reference system.")
                import pyproj

                parameters = pyproj.CRS.from_user_input(dataset.crs.to_wkt()).to_dict()
                if parameters.get("proj") != "stere" or float(parameters.get("lat_0", 0)) > -89.999:
                    raise HTTPException(502, "The LOLA product uses an unsupported coordinate reference frame.")
                radius_moon = float(parameters.get("R") or parameters.get("a") or 1_737_400.0)
                scale = float(parameters.get("k") or parameters.get("k_0") or 1.0)
                central_longitude = float(parameters.get("lon_0", 0.0))
                grid = PolarStereoGrid(dataset.transform[:6], (dataset.height, dataset.width), radius_moon, scale, central_longitude)
                x, y = grid.lonlat_to_xy(latitude_deg, longitude_deg_east)
                row, column = dataset.index(float(x), float(y))
                pixel_x = abs(float(dataset.transform.a))
                pixel_y = abs(float(dataset.transform.e))
                half_width = max(1, math.ceil(radius_km * 1000 / pixel_x))
                half_height = max(1, math.ceil(radius_km * 1000 / pixel_y))
                left, top = column - half_width, row - half_height
                window_width, window_height = half_width * 2, half_height * 2
                if left < 0 or top < 0 or left + window_width > dataset.width or top + window_height > dataset.height:
                    raise HTTPException(422, "The requested preview window falls outside NASA's 80–90°S LOLA hillshade coverage.")
                pixels = dataset.read(
                    1,
                    window=Window(left, top, window_width, window_height),
                    out_shape=(256, 256),
                    out_dtype="float32",
                    masked=True,
                    resampling=Resampling.bilinear,
                ).filled(float("nan"))
                png = _png_grayscale(pixels)
    except HTTPException:
        raise
    except ImportError as exc:
        raise HTTPException(503, "Rasterio and pyproj are required for remote LOLA previews.") from exc
    except Exception as exc:
        log.exception("Remote LOLA hillshade preview failed")
        raise HTTPException(502, "NASA's LOLA preview product could not be read. Check backend outbound access and retry.") from exc

    return Response(
        content=png,
        media_type="image/png",
        headers={
            "X-Terrain-Source": "NASA GSFC PGDA / LRO LOLA",
            "X-Terrain-Product": LOLA_HILLSHADE_PRODUCT,
            "X-Terrain-Resolution-M": "20",
            "X-Terrain-Coordinates": f"{latitude_deg:.6f}, {longitude_deg_east:.6f}",
            "X-Terrain-Display": "Contrast-stretched to the selected window for display",
            "Cache-Control": "public, max-age=86400",
        },
    )


class EphemerisReq(BaseModel):
    source: str = Field("horizons", pattern="^(horizons|observations|synthetic_test|none)$",
                        description="horizons = live JPL Horizons via Member 1's module; observations = rows supplied below; "
                                    "synthetic_test = fake tracks for demos; none = skip illumination/communication")
    observations: Optional[list[dict]] = Field(None, max_length=20000,
                                               description="Member 1 SiteObservation.to_dict() rows (datetime_utc, sun, earth)")


class PointReq(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=360)


class AnalyzeReq(BaseModel):
    config: dict = Field(default_factory=dict, description="AnalysisConfig overrides (lander, sim, scoring, uncertainty, ...)")
    ephemeris: EphemerisReq = Field(default_factory=EphemerisReq)
    point: Optional[PointReq] = None
    include_maps: bool = True
    allow_synthetic: bool = Field(True, description="Fall back to a labeled SYNTHETIC terrain when no real DEM is on disk")


class CompareReq(BaseModel):
    site_ids: list[int] = Field(min_length=2, max_length=6)
    config: dict = Field(default_factory=dict)
    ephemeris: EphemerisReq = Field(default_factory=EphemerisReq)
    allow_synthetic: bool = True


class EphemerisValidateReq(BaseModel):
    observations: list[dict] = Field(min_length=2, max_length=20000)


def _validate_config(cfg: AnalysisConfig):
    bad = []
    if not 0 <= cfg.uncertainty.runs <= 100: bad.append("uncertainty.runs must be 0..100")
    if not 1 <= cfg.lander.footprint_radius_m <= 200: bad.append("lander.footprint_radius_m must be 1..200")
    if not 100 <= cfg.window_radius_m <= 6000: bad.append("window_radius_m must be 100..6000")
    if not 36 <= cfg.n_azimuths <= 1440: bad.append("n_azimuths must be 36..1440")
    if not 1 <= cfg.sim.step_minutes <= 1440: bad.append("sim.step_minutes must be 1..1440")
    s = cfg.sim.resolved()
    if s.end_utc <= s.start_utc: bad.append("sim.end_utc must be after sim.start_utc")
    elif (s.end_utc - s.start_utc).days > 180: bad.append("simulation longer than 180 days is not allowed")
    if bad:
        raise HTTPException(422, "; ".join(bad))


async def _site(request: Request, site_id: int):
    row = await request.app.state.pool.fetchrow("SELECT id,name,pgda_key FROM sites WHERE id=$1", site_id)
    if not row:
        raise HTTPException(404, "Site not found")
    return dict(row)


def _get_bundle(site: dict, allow_synth: bool):
    key = site.get("pgda_key")
    if key:
        if key in _bundles:
            return _bundles[key]
        try:
            b = load_bundle(key, DATA_DIR)
            if len(_bundles) >= 2:
                _bundles.pop(next(iter(_bundles)))
            _bundles[key] = b
            return b
        except DatasetNotAvailable as e:
            if not allow_synth:
                raise HTTPException(404, f"{e}. Real terrain not downloaded; set allow_synthetic=true for a labeled synthetic demo.")
    elif not allow_synth:
        raise HTTPException(404, f"Site '{site['name']}' has no high-resolution LOLA product in the registry.")
    return make_synthetic_bundle()


def _sky_args(eph: EphemerisReq, site_name: str):
    if eph.source == "none":
        return None, None
    if eph.source == "observations":
        if not eph.observations:
            raise HTTPException(422, "ephemeris.observations required when source='observations'")
        try:
            return from_observation_dicts(eph.observations, {"source": "supplied observations (Member 1 format)"}), None
        except SkyDataError as e:
            raise HTTPException(422, f"Invalid ephemeris data: {e}")
    if eph.source == "synthetic_test":
        return "SYNTH", None
    def fn(lat, lon, alt_km, sim):
        return fetch_sky_series(site_name, lat, lon, alt_km, sim.start_utc, sim.end_utc, sim.step_minutes, CACHE_DIR)
    return None, fn


def _compute(bundle, cfg, sky, sky_fn, point, include_maps, label):
    if isinstance(sky, str):                                 # synthetic_test marker
        s = cfg.sim.resolved()
        sky = synthetic_sky(s.start_utc, (s.end_utc - s.start_utc).total_seconds() / 3600, max(1, s.step_minutes))
    return run_analysis(bundle, cfg, sky=sky, sky_fn=sky_fn, point=point, include_maps=include_maps, site_label=label)


async def _run(bundle, cfg, sky, sky_fn, point, include_maps, label):
    async with _sem:
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(loop.run_in_executor(None, _compute, bundle, cfg, sky, sky_fn, point, include_maps, label), TIMEOUT_S)
        except asyncio.TimeoutError:
            raise HTTPException(504, "Analysis timed out; reduce uncertainty.runs, the period, or window_radius_m")
        except ValueError as e:
            raise HTTPException(422, str(e))
        except SkyDataError as e:
            raise HTTPException(422, f"Invalid ephemeris data: {e}")
        except AstronomyUnavailable as e:
            raise HTTPException(503, f"{e}. Use ephemeris.source='observations' or 'none', or retry later.")
        except HTTPException:
            raise
        except Exception:
            log.exception("analysis failed")
            raise HTTPException(500, "Analysis failed (see server log)")


async def _store(request: Request, site_id, cfg, result, eph_source):
    try:
        rid = await request.app.state.pool.fetchval(
            "INSERT INTO analysis_runs(site_id,algorithm_version,dataset_real,ephemeris_source,status,score,config,result) "
            "VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id", site_id, ALGORITHM_VERSION, bool(result["dataset"]["real_data"]),
            eph_source, result["assessment"]["status"], result["assessment"]["score"], cfg.to_dict(), result)
        return rid
    except Exception:
        log.exception("could not persist analysis run")
        return None


@router.get("/defaults")
async def defaults():
    """Default configuration and the honesty notes that accompany every result."""
    return {"algorithm_version": ALGORITHM_VERSION, "config": AnalysisConfig().to_dict(),
            "notes": ["Lander criteria are DEMO DEFAULTS; set them to the real lander specification.",
                      "Scores use proposed demo weights, not NASA standards.",
                      "Geometric Earth visibility is not a radio link budget."]}


@router.get("/datasets")
async def datasets(request: Request):
    rows = await request.app.state.pool.fetch("SELECT id,name,pgda_key FROM sites WHERE pgda_key IS NOT NULL ORDER BY id")
    out = []
    for r in rows:
        a = registry.availability(r["pgda_key"], DATA_DIR)
        out.append({"site_id": r["id"], "site_name": r["name"], "pgda_key": r["pgda_key"], "pgda_name": a["name"],
                    "elevation_present": a["elevation_present"], "products_present": a["products"], "urls": a["urls"]})
    return {"source": registry.PRODUCT_PAGE, "lroc_reference": registry.LROC_ILLUMINATION,
            "data_dir": DATA_DIR, "sites": out,
            "fallback": "Sites without a downloaded DEM use a labeled SYNTHETIC terrain (dataset.real_data=false)."}


@router.post("/ephemeris/validate")
async def validate_ephemeris(req: EphemerisValidateReq):
    """Check a Member 1 observation series against the contract expected by the engine."""
    try:
        return {"valid": True, **from_observation_dicts(req.observations).summary()}
    except SkyDataError as e:
        raise HTTPException(422, str(e))


@router.post("/sites/{site_id}/analyze")
async def analyze(site_id: int, req: AnalyzeReq, request: Request):
    site = await _site(request, site_id)
    cfg = config_from_dict(req.config)
    _validate_config(cfg)
    bundle = await asyncio.get_running_loop().run_in_executor(None, _get_bundle, site, req.allow_synthetic)
    sky, sky_fn = _sky_args(req.ephemeris, site["name"])
    result = await _run(bundle, cfg, sky, sky_fn, req.point.model_dump() if req.point else None, req.include_maps, site["name"])
    result["db_site_id"] = site_id
    result["run_id"] = await _store(request, site_id, cfg, clean(result), req.ephemeris.source)
    return result


@router.post("/compare")
async def compare(req: CompareReq, request: Request):
    """Analyse several sites with identical settings and rank them (eligible before rejected)."""
    cfg = config_from_dict(req.config)
    _validate_config(cfg)
    cfg.uncertainty.runs = min(cfg.uncertainty.runs, 20)
    results = []
    for sid in req.site_ids:
        site = await _site(request, sid)
        bundle = await asyncio.get_running_loop().run_in_executor(None, _get_bundle, site, req.allow_synthetic)
        sky, sky_fn = _sky_args(req.ephemeris, site["name"])
        r = await _run(bundle, cfg, sky, sky_fn, None, False, site["name"])
        r["db_site_id"] = sid
        results.append(r)
    ranked = rank_sites(results)
    return {"ranking": [{"rank": r["rank"], "site": r["site_name"], "db_site_id": r["db_site_id"],
                         "status": r["assessment"]["status"], "score": r["assessment"]["score"],
                         "real_data": r["dataset"]["real_data"], "illumination_percent": (r["illumination"] or {}).get("percent_illuminated"),
                         "earth_visibility_percent": (r["communication"] or {}).get("visibility_percent"),
                         "footprint_status": r["hazards"]["footprint_status"]} for r in ranked],
            "note": "Sites with a failed hard constraint rank below all others regardless of score.", "results": ranked}


@router.get("/runs/{run_id}")
async def get_run(run_id: int, request: Request):
    row = await request.app.state.pool.fetchrow("SELECT id,site_id,created_at,config,result FROM analysis_runs WHERE id=$1", run_id)
    if not row:
        raise HTTPException(404, "Run not found")
    return {"run_id": row["id"], "site_id": row["site_id"], "created_at": row["created_at"].isoformat(),
            "config": row["config"], "result": row["result"]}


@router.get("/sites/{site_id}/runs")
async def site_runs(site_id: int, request: Request):
    rows = await request.app.state.pool.fetch(
        "SELECT id,created_at,dataset_real,ephemeris_source,status,score FROM analysis_runs WHERE site_id=$1 ORDER BY id DESC LIMIT 20", site_id)
    return [{**dict(r), "created_at": r["created_at"].isoformat()} for r in rows]
