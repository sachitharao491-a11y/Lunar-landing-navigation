# Integration plan: Member 2 terrain and mission-analysis engine

> Historical integration/design notes from the original merge. Statements below about the initial ZIP contents, team members, or build environment describe that earlier work record; consult the root README and audit documents for the current package state.

## 1. What exists today (inspected)
`nasa_app.zip` contained the Lunar Moon Navigator full-stack build (FastAPI + asyncpg + PostGIS + single-file Three.js front end).
`astronomy.zip` (and an identical `astronomy_1.zip`) is **Member 1's module**: a JPL Horizons client, geometry/solar/Earth-visibility
calculations, a data model, validation scripts, 98 tests and a small FastAPI app. No Member 3 (frontend) or Member 4 (backend) code was supplied, so those
interfaces are defined by explicit JSON contracts (section 4).

| Existing piece | Role | Reuse / change |
|---|---|---|
| `backend/app/main.py` (FastAPI, pool, JWT auth) | API host | Reused. Add one `include_router` line. |
| `backend/app/scoring.py` | Demo scoring from hand-entered sample values | Kept unchanged (demo/educational). The new engine scores from real terrain. |
| `db/schema.sql`, `seed.sql` | Sites with sample attributes | Kept. New idempotent migration `db/002_terrain.sql` adds `sites.pgda_key`, `terrain_datasets`, `analysis_runs`. |
| `frontend/index.html` | 3D Moon, planner, analysis UI | Kept. Add one sidebar view, "Terrain Analysis". No existing feature changed. |
| `docker-compose.yml` | db + api | Mount `./data` into the API container; mount the migration. |

## 2. Mapping the spec onto this architecture (no second application)
The spec proposes a standalone `lunar-terrain-engine/` repo. Here it becomes a **sub-package of the
existing backend**, `backend/app/terrain/`, keeping the spec's module names:

```
backend/app/terrain/
  config.py                 LanderSpec, SimulationConfig, ScoringConfig, UncertaintyConfig
  ingestion/                dem_loader, registry (PGDA products), quality_control, synthetic
  geometry/                 coordinates (polar stereographic <-> MOON_ME), surface_normals, horizon (3D ray casting)
  surface/                  derivatives (slope, aspect, roughness, curvature, relief)
  hazards/                  crater_detection, safety_assessment (footprint, obstacles)
  illumination/             windows (interval logic), sun_visibility
  communication/            earth_visibility
  ephemeris/                SkySeries, Member 1 (JPL Horizons) adapter with cache, synthetic test tracks
  scoring/                  site_ranking (hard-constraint gate)
  validation/               uncertainty (Monte Carlo), reference (NASA slope / LROC comparison)
  pipeline.py               orchestrates engines -> spec output contract
backend/astronomy/          Member 1's package, vendored unchanged
backend/app/api_terrain.py  FastAPI router /api/analysis/*
scripts/                    download_data.py, generate_maps.py, validate_against_nasa.py
docs/                       this plan, TERRAIN_ENGINE.md (algorithms, assumptions, contracts)
```

## 3. Decisions that differ from the spec (with reasons)
1. **Ray casting uses a DEM horizon profile, not a PyVista/Open3D mesh.** For a height field and a point
   observer this is mathematically the same visibility test (a body is blocked iff its elevation is below the
   terrain horizon in that azimuth), includes Moon curvature, needs no mesh, and is cheap enough to run
   100 Monte Carlo realizations. Mesh ray casting is listed as future work.
2. **No Numba, GeoPandas, Shapely, or SpiceyPy**: not needed by the implemented algorithms. Runtime dependencies are
   numpy, scipy, rasterio, and pyproj for terrain processing.
3. **Thresholds are never invented.** `LanderSpec` values default to clearly labeled *demo defaults*; every
   result echoes `criteria_source` so nothing is presented as a mission requirement.
4. **Real NASA data cannot be bundled** (hundreds of MB to GB). `scripts/download_data.py` downloads the
   official PGDA LOLA products. Until they are on disk, the API falls back to a **labeled synthetic terrain**
   (`dataset.real_data = false`), shown with a red banner in the UI.

## 4. Contracts with the other members (updated after inspecting Member 1's module)
* **Member 1 -> us.** Their `astronomy/` package returns *topocentric* Sun/Earth azimuth, elevation and range for a lunar site from JPL Horizons
  (airless apparent, 1-minute resolution). It explicitly excludes local terrain, which is exactly what this engine adds. The planned MOON_ME-vector contract was therefore
  replaced by their real output. The package is vendored **unchanged** in `backend/astronomy/` (verified byte-identical), called through `ephemeris/astronomy_adapter.py`
  (cached, validated), and its disk-visibility helpers are reused rather than duplicated. Their FastAPI app is mounted at `/api/astronomy`.
* **Us -> Member 4.** One JSON result per site (spec schema + provenance, units, intervals, `null` for unknown); stored in `analysis_runs`.
* **Us -> Member 3.** The same JSON plus downsampled `maps`, `horizon` profile and interval lists; the Terrain Analysis view in `frontend/index.html` is a working reference consumer.

## 5. Stages
1. Data layer: registry, loader, QC, synthetic fixture, DB migration, download script.
2. Terrain + hazards: derivatives, crater/obstacle detection, footprint assessment (PASS/WARNING/FAIL/UNKNOWN).
3. Visibility: horizon ray casting, illumination windows, Earth line-of-sight and blackouts.
4. Intelligence: scoring with hard-constraint gate, Monte Carlo uncertainty, reference comparison.
5. Integration: FastAPI router, persistence, front-end view.
6. Tests and docs.
