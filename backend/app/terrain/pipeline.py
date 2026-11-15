"""Terrain analysis pipeline: DEM + (optional) Member 1 sky series -> spec-conformant result dict.

Stages: point selection -> quality control -> terrain derivatives -> crater/obstacle/footprint hazards ->
horizon ray casting -> sunlight windows -> Earth line-of-sight windows -> Monte Carlo -> scoring -> provenance.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Callable, Optional

import numpy as np
from scipy.ndimage import maximum_filter

from .communication.earth_visibility import analyze_earth_visibility
from .config import ALGORITHM_VERSION, AnalysisConfig
from .geometry.coordinates import R_REF_M
from .geometry.horizon import horizon_profile, interp_horizon, sample_dem
from .geometry.surface_normals import surface_normal_enu
from .hazards.crater_detection import detect_craters
from .hazards.safety_assessment import evaluate_point, hazard_map, terrain_layers
from .illumination.sun_visibility import analyze_illumination
from .ingestion.dem_loader import DEMBundle
from .ingestion.quality_control import assess_quality
from .scoring.site_ranking import assess
from .surface.derivatives import aspect_deg, curvature, disk_footprint, slope_deg
from .validation.reference import slope_vs_nasa
from .validation.uncertainty import monte_carlo, perturbation_field

SkyFn = Callable[[float, float, float, object], object]


def clean(o):
    """Make a structure JSON-safe: numpy -> python, NaN/inf -> None, datetimes -> ISO strings."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return o


def _downsample(a, n=96, how="mean"):
    f = int(math.ceil(max(a.shape) / n))
    if f <= 1:
        return a, 1
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    blk = a[:h, :w].reshape(h // f, f, w // f, f)
    with np.errstate(all="ignore"):
        out = np.nanmax(blk, axis=(1, 3)) if how == "max" else np.nanmean(blk, axis=(1, 3))
    return out, f


def auto_select_point(bundle: DEMBundle, cfg: AnalysisConfig):
    """Pixel whose landing footprint has the smallest maximum slope (terrain screening only)."""
    spec, px = cfg.lander, bundle.px
    margin = int(math.ceil((spec.footprint_radius_m + spec.clearance_margin_m) / px)) + cfg.normal_window_px + 2
    z, grid, r0, c0 = bundle.elev, bundle.grid, 0, 0
    if z.size > 9e6:
        side = int(9e6 ** 0.5)
        r0, c0 = (z.shape[0] - side) // 2, (z.shape[1] - side) // 2
        z = z[r0:r0 + side, c0:c0 + side]
        grid = grid.subgrid(r0, c0, z.shape)
    sl = slope_deg(z, grid.pixel_x, grid.pixel_y, grid.scale_grid())
    smax = maximum_filter(np.where(np.isfinite(sl), sl, np.inf), footprint=disk_footprint(spec.footprint_radius_m / px))
    smax[:margin] = smax[-margin:] = np.inf
    smax[:, :margin] = smax[:, -margin:] = np.inf
    if not np.isfinite(smax.min()):
        raise ValueError("No valid landing footprint found in this tile")
    r, c = np.unravel_index(np.argmin(smax), smax.shape)
    return int(r + r0), int(c + c0)


def run_analysis(bundle: DEMBundle, cfg: AnalysisConfig, sky=None, sky_fn: Optional[SkyFn] = None,
                 point: Optional[dict] = None, include_maps: bool = True, site_label: str | None = None) -> dict:
    spec, sim = cfg.lander, cfg.sim.resolved()
    px = bundle.px
    H, W = bundle.elev.shape
    warnings, notes = [], []

    # ---- 1. analysis point -------------------------------------------------------------------
    selected = "tile_centre"
    if point and point.get("lat") is not None and point.get("lon") is not None:
        r, c = bundle.grid.lonlat_to_rowcol(float(point["lat"]), float(point["lon"]))
        selected = "user_lat_lon"
    elif point and point.get("row") is not None:
        r, c, selected = point["row"], point["col"], "user_row_col"
    elif cfg.auto_select_point:
        r, c = auto_select_point(bundle, cfg)
        selected = "auto_lowest_footprint_slope"
    else:
        r, c = H // 2, W // 2
    rc = (int(round(float(r))), int(round(float(c))))
    margin = int(math.ceil((spec.footprint_radius_m + spec.clearance_margin_m) / px)) + cfg.normal_window_px + 2
    if not (margin <= rc[0] < H - margin and margin <= rc[1] < W - margin):
        raise ValueError(f"Analysis point (row {rc[0]}, col {rc[1]}) is closer than {margin} px to the tile edge or outside it")
    lat, lon = (float(v) for v in bundle.grid.rowcol_to_lonlat(*rc))
    x_m, y_m = (float(v) for v in bundle.grid.rowcol_to_xy(*rc))
    z0 = float(bundle.elev[rc])
    if not np.isfinite(z0):
        raise ValueError("Elevation at the analysis point is missing (NoData)")

    # ---- 2. window + quality ---------------------------------------------------------------------
    half = int(math.ceil(cfg.window_radius_m / px))
    r0, c0 = max(0, rc[0] - half), max(0, rc[1] - half)
    win = bundle.window(r0, rc[0] + half + 1, c0, rc[1] + half + 1)
    rc_w = (rc[0] - r0, rc[1] - c0)
    qkw = dict(ref_sigma_z=cfg.scoring.ref_sigma_z_m, ref_sigma_slope=cfg.scoring.ref_sigma_slope_deg,
               target_measured=cfg.scoring.target_measured_fraction)
    q_tile = assess_quality(bundle.elev, bundle.count, bundle.z_err, bundle.slope_err, **qkw)
    q_win = assess_quality(win.elev, win.count, win.z_err, win.slope_err, **qkw)
    warnings += q_win["warnings"]

    # ---- 3. terrain + hazards --------------------------------------------------------------------
    L = terrain_layers(win.elev, win.grid, spec, win.slope_err)
    craters = detect_craters(win.elev, px, L["slope"], win.grid)
    fp = evaluate_point(win.elev, L, rc_w, spec, craters, win.count)
    inner = (slice(5, -5), slice(5, -5))
    sl_in = L["slope"][inner]
    asp = aspect_deg(win.elev, win.grid.pixel_x, win.grid.pixel_y, L["scale"])
    curv = curvature(win.elev, win.grid.pixel_x, win.grid.pixel_y, L["scale"])
    zv = win.elev[np.isfinite(win.elev)]
    terrain = {
        "mean_slope_deg": float(np.nanmean(sl_in)), "median_slope_deg": float(np.nanmedian(sl_in)),
        "p95_slope_deg": float(np.nanpercentile(sl_in, 95)), "max_slope_deg": float(np.nanmax(sl_in)),
        "roughness_m": float(np.nanmedian(L["rough"])), "elevation_range_m": [float(zv.min()), float(zv.max())],
        "elevation_at_point_m": z0, "slope_at_point_deg": float(L["slope"][rc_w]),
        "aspect_at_point_grid_deg": None if not np.isfinite(asp[rc_w]) else float(asp[rc_w]),
        "curvature_at_point_per_m": float(curv[rc_w]), "window_radius_m": cfg.window_radius_m,
        "footprint_max_slope_deg": fp["max_slope_deg"], "footprint_relief_m": fp["relief_m"],
        "footprint_roughness_p95_m": fp["roughness_p95_m"],
        "aspect_note": "Aspect is measured from GRID north (+y), not true lunar north.",
    }
    hazards = {"footprint_status": fp["footprint_status"], "obstacle_count": fp["obstacle_count"],
               "uncertain_area_percent": fp["uncertain_area_percent"], "checks": fp["checks"],
               "craters_detected": len(craters), "crater_candidates": craters[:10]}

    # ---- 4. horizon ray casting + normal --------------------------------------------------------
    normal = surface_normal_enu(bundle.grid, bundle.elev, rc[0], rc[1], cfg.normal_window_px)
    hz_sun = horizon_profile(bundle.grid, bundle.elev, lat, lon, sim.sun_height_m, cfg.n_azimuths)
    hz_ant = horizon_profile(bundle.grid, bundle.elev, lat, lon, sim.antenna_height_m, cfg.n_azimuths)
    edge_frac = float(hz_sun["edge_limited"].mean())

    # ---- 5. Sun / Earth ---------------------------------------------------------------------------
    sky_info, illum, comm = None, None, None
    if sky is None and sky_fn is not None:
        sky = sky_fn(lat, lon, (z0 + sim.sun_height_m) / 1000.0, sim)
    if sky is not None:
        site = sky.provenance.get("site")
        if site:
            dla = abs(site["lat_deg"] - lat) * R_REF_M * math.pi / 180
            if dla > 500:
                warnings.append(f"Sky series was computed for a site {dla:.0f} m from the analysis point; directions may be inaccurate.")
        else:
            warnings.append("Sky series has no site metadata; cannot verify it belongs to this analysis point.")
        illum = analyze_illumination(sky, hz_sun, normal, sim)
        comm = analyze_earth_visibility(sky, hz_ant, sim)
        sky_info = sky.summary()
        warnings += list(sky.warnings)
    else:
        notes.append("No Sun/Earth ephemeris supplied: illumination and communication were not computed.")

    # ---- 6. Monte Carlo ---------------------------------------------------------------------------
    mc = None
    unc = cfg.uncertainty
    if unc.runs > 0:
        corr = unc.corr_length_m / px
        do_vis = unc.include_visibility and sky is not None and unc.runs <= unc.max_visibility_runs
        if unc.include_visibility and not do_vis:
            notes.append("Visibility Monte Carlo skipped (no sky series or runs > max_visibility_runs).")
        zerr = win.z_err if win.z_err is not None else 1.0
        if win.z_err is None:
            warnings.append("No elevation-uncertainty layer: Monte Carlo uses a 1.0 m fallback sigma (assumption).")

        def perturb(rng):
            if do_vis:
                ze = bundle.z_err if bundle.z_err is not None else 1.0
                full = perturbation_field(bundle.elev.shape, ze, corr, rng)
                return full
            return perturbation_field(win.elev.shape, zerr, corr, rng)

        def evaluate(p):
            pw = p[r0:r0 + win.elev.shape[0], c0:c0 + win.elev.shape[1]] if do_vis else p
            ez = win.elev + pw
            Lp = terrain_layers(ez, win.grid, spec, win.slope_err)
            res = evaluate_point(ez, Lp, rc_w, spec, craters, win.count)
            out = {"status": res["footprint_status"], "max_slope_deg": res["max_slope_deg"]}
            if do_vis:
                ef = bundle.elev + p
                h1 = horizon_profile(bundle.grid, ef, lat, lon, sim.sun_height_m, 360)
                h2 = horizon_profile(bundle.grid, ef, lat, lon, sim.antenna_height_m, 360)
                out["illumination_percent"] = analyze_illumination(sky, h1, normal, sim)["percent_illuminated"]
                out["communication_percent"] = analyze_earth_visibility(sky, h2, sim)["visibility_percent"]
            return out

        mc = monte_carlo(unc.runs, unc.seed, perturb, evaluate)
        mc["includes_visibility"] = bool(do_vis)
        mc["crater_candidates"] = "held fixed across realizations"

    # ---- 7. validation vs NASA products -------------------------------------------------------------
    validation = {"slope_vs_nasa_product": slope_vs_nasa(L["slope"], win.nasa_slope) if win.nasa_slope is not None
                  else {"status": "not_available", "reason": "NASA slope product (slp) not loaded for this site"},
                  "illumination_vs_lroc": {"status": "not_run", "reason": "Provide an LROC reference value via scripts/validate_against_nasa.py"}}

    # ---- 8. scoring -----------------------------------------------------------------------------------
    assessment = assess(fp, illum, comm, q_win, mc, spec, cfg.scoring)

    limits = [
        f"DEM heights assumed relative to sphere R={bundle.grid.R:.0f} m (verify against the PGDA README).",
        f"Obstruction beyond the DEM tile edge is not evaluated; {100 * edge_frac:.0f}% of azimuths have their horizon limited by the tile edge.",
        "A 5 m DEM cannot resolve boulders or craters smaller than ~15 m; most PGDA pixels are interpolated, not measured.",
        "Horizon ray sampling is 1 pixel within 2 km and grows 1% per step beyond; narrow distant ridges may be missed.",
        "Sun/Earth directions are JPL Horizons airless apparent values (Member 1); eclipses of the Sun by Earth are not modelled.",
        "Earth visibility is geometric line of sight only, not a radio link budget.",
        "Monte Carlo perturbations are synthetic correlated fields, not NASA's DEM clones; the result is a confidence indicator, not a probability of success.",
    ]
    if spec.criteria_source == "DEMO_DEFAULTS":
        limits.insert(0, "Landing criteria are DEMO DEFAULTS, not a lander specification or mission requirement.")
    if not bundle.real_data:
        limits.insert(0, "SYNTHETIC terrain: results demonstrate the software only and say nothing about the real Moon.")

    horizon_out = {"azimuth_deg": list(range(360)),
                   "sun_horizon_deg": np.round(interp_horizon(hz_sun, np.arange(360)), 3),
                   "antenna_horizon_deg": np.round(interp_horizon(hz_ant, np.arange(360)), 3),
                   "edge_limited_fraction": edge_frac, "missing_sample_fraction": hz_sun["missing_fraction"],
                   "observer_heights_m": {"sun": sim.sun_height_m, "antenna": sim.antenna_height_m},
                   "azimuth_convention": "0=North clockwise (local, Horizons convention)"}

    result = {
        "site_id": (bundle.key or "SITE").upper().replace("SITE", "SITE_") if str(bundle.key).startswith("Site") else bundle.key,
        "site_name": site_label or bundle.name,
        "dataset": {"source": bundle.meta.get("source"), "real_data": bundle.real_data,
                    "resolution_m": bundle.meta.get("resolution_m"), "coordinate_frame": bundle.meta.get("coordinate_frame"),
                    "height_reference": bundle.meta.get("height_reference"), "data_quality": q_win["data_quality"],
                    "product_page": bundle.meta.get("product_page"), "files": bundle.meta.get("files"),
                    "shape_px": [H, W], "grid": bundle.grid.describe(), "quality_tile": q_tile, "quality_window": q_win},
        "analysis_point": {"lat_deg": lat, "lon_deg_east": lon, "row": rc[0], "col": rc[1], "x_m": x_m, "y_m": y_m,
                           "ground_elevation_m": z0, "selection": selected},
        "terrain": terrain, "hazards": hazards,
        "illumination": None if illum is None else {**illum, "illumination_percent": illum["percent_illuminated"]},
        "communication": comm,
        "horizon": horizon_out, "uncertainty": mc, "validation": validation, "assessment": assessment,
        "provenance": {"algorithm_version": ALGORITHM_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
                       "config": cfg.to_dict(), "sky": sky_info,
                       "simulation_interval": {"start_utc": sim.start_utc, "end_utc": sim.end_utc,
                                               "step_minutes": sim.step_minutes}},
        "limitations": limits, "warnings": list(dict.fromkeys(warnings)), "notes": notes,
    }
    if include_maps:
        sl_ds, f = _downsample(L["slope"], 96, "mean")
        hm, smax = hazard_map(win.elev, L, spec)
        hz_ds, _ = _downsample(hm.astype(float), 96, "max")
        ds_elev, _ = _downsample(win.elev, 96, "mean")
        result["maps"] = {"downsample_factor": f, "pixel_m": px * f, "extent_m": [win.elev.shape[1] * px, win.elev.shape[0] * px],
                          "point_rc": [rc_w[0] / f, rc_w[1] / f], "footprint_radius_px": spec.footprint_radius_m / (px * f),
                          "slope_deg": np.round(sl_ds, 1), "elevation_m": np.round(ds_elev, 1),
                          "hazard_class": hz_ds.astype(int),
                          "hazard_legend": {"0": "PASS", "1": "WARNING", "2": "FAIL", "3": "UNKNOWN"},
                          "note": "Hazard class per pixel = footprint max slope / relief / missing data vs configured limits."}
    return clean(result)
