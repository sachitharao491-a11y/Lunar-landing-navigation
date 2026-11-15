# Terrain & Mission Analysis Engine (Member 2)

Scientific analysis subsystem inside Lunar Moon Navigator: real NASA LOLA elevation data + Member 1's JPL Horizons
Sun/Earth directions -> landing-footprint hazards, terrain-aware sunlight, Earth line-of-sight, site scoring, uncertainty.

> **Scope and validation.** The engine, API, database migration, and front-end view are implemented. This document records test coverage and assumptions, not a claim that the current archive has passed a new validation run. Synthetic known-answer tests do not validate the engine against real lunar rasters. Run `scripts/download_data.py` and `scripts/validate_against_nasa.py` before presenting real-data numbers. Results are a research prototype, not a certified landing-safety assessment or a NASA recommendation. Current audit test results are reported separately with the project revision.

## 1. Data flow

```
NASA PGDA LOLA 5 m GeoTIFFs (surf, ldec, slp, toterr, slperr)           Member 1 (astronomy/) -> JPL Horizons
        |  ingestion: CRS check, NoData, QC                                   |  Sun & Earth az/el/range per site
        v                                                                      v
 DEMBundle --> terrain derivatives --> hazards (craters, footprint)      SkySeries (validated, cached)
        |                                                                      |
        +--> horizon ray casting (3D, curvature) ---> sunlight windows, Earth windows, blackouts
        +--> Monte Carlo (TOTERR) ------------------> confidence indicator
        +--> scoring with hard-constraint gate -----> status + score  ---> JSON ---> API ---> Member 3/4
```

## 2. Spec traceability (Member 2 plan -> implementation)

| Plan item | Where | Status |
|---|---|---|
| DEM ingestion + metadata/CRS validation | `ingestion/dem_loader.py`, `registry.py` | Implemented; **unverified on real files** |
| Slope, aspect, roughness (detrended), curvature, relief | `surface/derivatives.py` | Implemented, tested |
| Landing footprint (configurable), obstacles, craters, missing/uncertain data, clearance ring | `hazards/` | Implemented, tested |
| PASS / WARNING / FAIL / UNKNOWN | `hazards/safety_assessment.py` | Implemented, tested (FAIL > UNKNOWN > WARNING > PASS) |
| Sunlight: horizon test, shadow, hours, longest light/dark, sunrise/sunset | `illumination/` | Implemented, tested vs analytic cases |
| Earth line of sight, windows, blackouts (with reason) | `communication/` | Implemented, tested |
| Weighted scoring + hard constraints | `scoring/site_ranking.py` | Implemented, tested |
| Data confidence, uncertainty layers, missing masks | `ingestion/quality_control.py` | Implemented, tested |
| Monte Carlo uncertainty | `validation/uncertainty.py` | Implemented, tested (synthetic fields, not NASA clones) |
| Reference comparison (NASA slope, LROC illumination) | `validation/reference.py`, `scripts/validate_against_nasa.py` | Implemented; **needs real data to run** |
| FastAPI endpoints + schemas | `api_terrain.py` (OpenAPI at `/docs`) | Implemented; compile-checked only |
| Tests | `backend/tests/` | 34 engine tests + 6 existing = 40; all pass |
| 3D terrain **mesh** (PyVista/Open3D) | n/a | **Not implemented**: height-field horizon ray casting is the exact equivalent for a point observer |
| Numba, GeoPandas, Shapely, Hough transform, SPICE kernels | n/a | Not needed / not implemented (Member 1 uses Horizons, not SPICE) |

## 3. Algorithms (what the code actually does)

* **Frame and grid.** PGDA rasters are south-polar-stereographic (metres, MOON_ME). `PolarStereoGrid` implements the spherical
  forward/inverse with scale factor `k = 2k0/(1+cos c)`; CRS parameters are read from the file via pyproj and **refused if not a
  south polar stereographic**. Slope uses ground spacing `pixel/k`.
* **Slope/aspect:** 3-point gradient (or Horn 3x3). Aspect is relative to *grid* north, flagged in output.
* **Roughness:** RMS of elevation after removing the best-fit plane in a window; windows overhanging the array are NaN (never fake zeros).
* **Craters:** per scale, `enclosed_depth = 2nd-lowest rim-sector mean - interior mean` over 8 sectors (bounded on >=7 of 8 sides), local maxima,
  depth and depth/diameter thresholds, wall-slope verification, cross-scale suppression. Candidates only. Tested: finds known craters, no false positives on ridge-only or plain terrain.
* **Footprint:** disk of `footprint_radius_m`; checks max slope, relief, p95 roughness, crater wall/rim crossing (a footprint wholly on a crater *floor* is reported, not failed),
  obstacles (positive features > `obstacle_height_m`), clearance-ring slope, missing data (UNKNOWN above threshold), and `slope + k*sigma` vs limit (WARNING).
* **Horizon ray casting.** For observer `O` and azimuth `a`, terrain points along the great circle are `P = (R+z) u(s)`; elevation of `P` seen from `O` is
  `atan2((P-O).up, |(P-O)_h|)`. Horizon = max over distance. A body at elevation `el` is blocked iff `el <= horizon(a)`. Curvature is inherent; tested against a 50 m wall at 1 km
  (2.860 deg vs analytic 2.862 deg) and a flat sphere (horizon dips below 0).
* **Sunlight.** `lit = (Sun disk fraction above terrain horizon > threshold) AND (n . s > 0)`. Disk fraction reuses Member 1's `compute_visible_fraction`/`compute_angular_radius`.
  Transitions are refined by bisection on interpolated unit vectors to `refine_s` (tested: sunrise within 1 s of the analytic value).
* **Earth.** Visible iff centre elevation > max(terrain horizon, antenna mask). Blackout intervals carry a reason: `below_local_horizon`, `terrain_blocked`, `below_antenna_mask`.
  **Geometric only, not a link budget.**
* **Scoring.** `S = sum w_i s_i / sum w_i` over *available* components; missing components are listed, never zero-filled.
  Status is decided by the footprint assessment first: a failed hard constraint gives `REJECTED_HARD_CONSTRAINT` whatever the score; ranking sorts status class first, score second.
* **Monte Carlo.** Correlated Gaussian fields scaled by TOTERR (fallback 1.0 m, flagged). Output is the share of realizations that PASS, labeled a *confidence indicator*, not a probability.

## 4. Contracts

### Member 1 -> engine (implemented against their real code)
Member 1's module (`backend/astronomy/`, vendored unchanged) returns **topocentric** Sun/Earth azimuth, elevation and range from JPL Horizons (airless apparent, 1-minute resolution).
So the contract is the per-site observation, not MOON_ME vectors. `ephemeris/astronomy_adapter.py` calls their `query_body_range` for Sun and Earth, validates, caches
(`data/cache/horizons`) and returns a `SkySeries`. The engine passes `altitude_km = (DEM height + observer height)/1000` so Horizons uses the true site height.
Accepted JSON rows (also `SiteObservation.to_dict()`): `{"datetime_utc": ISO-8601 with tz, "sun": {"azimuth_deg","elevation_deg","range_km"}, "earth": {...}}`.
Validate with `POST /api/analysis/ephemeris/validate`. Member 1's own API is mounted at `/api/astronomy`.

### Engine -> Member 4 (backend) and Member 3 (frontend)
`POST /api/analysis/sites/{id}/analyze` returns the spec schema with additions: `dataset`, `analysis_point`, `terrain`, `hazards{footprint_status,checks[],obstacle_count,uncertain_area_percent}`,
`illumination{sunlight_hours,darkness_hours,illumination_percent,...intervals,transitions}`, `communication{earth_visible_at_start,visibility_hours,blackout_intervals[]}`,
`uncertainty`, `assessment{score,status}`, `horizon`, `maps{slope_deg,elevation_m,hazard_class}`, `provenance`, `limitations[]`, `warnings[]`. Unknown values are `null`, never `0`.

| Endpoint | Purpose |
|---|---|
| `GET /api/analysis/defaults` | default configuration + honesty notes |
| `GET /api/analysis/datasets` | which NASA products are on disk per site, with source URLs |
| `POST /api/analysis/ephemeris/validate` | validate a Member 1 series |
| `POST /api/analysis/sites/{id}/analyze` | full analysis (stored in `analysis_runs`) |
| `POST /api/analysis/compare` | analyse up to 6 sites with identical settings and rank them |
| `GET /api/analysis/runs/{id}`, `GET /api/analysis/sites/{id}/runs` | retrieve stored results |

Ephemeris `source`: `horizons` (live), `observations` (rows supplied), `synthetic_test` (demo tracks, labeled), `none` (terrain only).

## 5. Real data: how to use it

```bash
pip install -r backend/requirements.txt
python scripts/download_data.py --list
python scripts/download_data.py --site Site04            # surf, ldec, slp, toterr, slperr (large files)
python scripts/validate_against_nasa.py --site Site04    # slope vs NASA product; optional LROC check
docker compose up --build                                # ./data is mounted into the container
```
Source: NASA GSFC PGDA, *High-Resolution LOLA Topography for Lunar South Pole Sites* (https://pgda.gsfc.nasa.gov/products/78). LROC illumination references: `WAC_POLE_ILL_PCT_SOUTH`, `WAC_POLE_ILL_TWI_SOUTH`.
Without downloaded files the API uses a **labeled synthetic terrain** (`dataset.real_data=false`, red banner in the UI).

## 6. Assumptions to verify on first real run (recorded in every result's provenance)

1. DEM heights are relative to a sphere of R = 1,737,400 m (`height_reference`). Confirm in the PGDA README.
2. The GeoTIFF CRS is a south polar stereographic on a sphere; the loader reads it and refuses otherwise.
3. Horizons uses geodetic/planetographic site coordinates, the DEM planetocentric; identical for a spherical Moon (Member 1 lists this as an open question).
4. Horizons local north equals the DEM frame's north (both MOON_ME / DE421).
5. `Clones/*_err.tif` semantics (offset vs absolute DEM) were **not** verified (the NASA README could not be read); the engine does not use clones yet.
6. NASA's slope product may use a different baseline; differences are reported by `validate_against_nasa.py`, not hidden.

## 7. Known limitations

* Obstruction beyond the DEM tile edge is not evaluated; the fraction of azimuths limited by the edge is reported (`horizon.edge_limited_fraction`).
* ~90% of 5 m pixels are interpolated; boulders and craters below ~15 m are not resolved.
* Ray sampling is 1 pixel to 2 km then +1% per step; narrow distant ridges may be missed.
* Solar eclipses by Earth are not modelled; the Sun's disk uses Member 1's circular-segment approximation.
* Criteria and scoring weights are demo defaults, not lander requirements or NASA standards.
* Visibility Monte Carlo is optional and slow; crater candidates are held fixed across realizations.

## 8. Tests

`cd backend && python -m pytest tests/` (or `python tests/run_all.py`). The suite covers scenarios in the plan's test table (flat terrain, constant surface, steep hill, crater,
Sun overhead, Sun behind mountain, Earth below horizon, missing pixels, higher uncertainty, failed constraint) plus coordinates, horizon known answers, rise-time refinement,
contract validation, adapter + cache against Member 1's real data types, scoring gate, ranking, determinism and JSON safety.
Member 1's "Live" tests call JPL Horizons and need network access.
