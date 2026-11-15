# Architecture and data flow

## Runtime shape

The project has a React + TypeScript frontend, a FastAPI service, and PostgreSQL with PostGIS. Vite compiles `frontend/src/` to `frontend/dist/`; FastAPI serves that build. The earlier static interface remains preserved in the repository as a reference.

```text
React + TypeScript UI
  | typed API requests (same origin in production)
  v
FastAPI
  |-- asyncpg ----------------> PostgreSQL / PostGIS
  |-- astronomy package ------> JPL Horizons API
  |-- httpx ------------------> NASA Image and Video Library
  `-- terrain engine <-------- local PGDA LOLA GeoTIFFs
```

The active frontend is organized under `frontend/src/`: reusable React components, typed API services, response types, and responsive styles. Vite proxies `/api` to the local backend during development. The earlier static app files and standalone demo are preserved but are not used by the production bundle.
## Backend packages

- `backend/app/main.py` defines the application lifecycle, database pool, authentication, site and plan endpoints, NASA media proxy, and static-file serving.
- `frontend/src/services/api.ts` is the active frontend API boundary. It uses existing backend routes, checks key response shapes, and reports request errors without local scientific fallback values.
- `frontend/src/components/` renders backend site records, Horizons observations, comparisons, real-DEM terrain availability, and source provenance.
- `backend/app/scoring.py` calculates educational suitability scores from the sample database attributes. The terrain ranking is separate and lives in `backend/app/terrain/scoring/site_ranking.py`.
- `backend/app/terrain/` contains the project-specific terrain-analysis pipeline: DEM ingestion, coordinate transforms, derivatives, crater/depression candidates, landing-footprint checks, horizon rays, illumination windows, Earth visibility, scoring, and uncertainty propagation.
- `backend/astronomy/` is the team astronomy contribution. It constructs and parses Horizons observer requests, calculates geometric Sun/Earth visibility, and provides a small FastAPI application mounted under `/api/astronomy`.
- `backend/app/api_terrain.py` adapts database sites and request configuration to the terrain package and persists run provenance/results.

## Terrain-analysis flow

1. `/api/analysis/datasets` lists database sites and indicates whether an elevation raster is present in `TERRAIN_DATA_DIR`.
2. The engine loads local PGDA LOLA rasters when available. The API supports labeled synthetic test data, but the active frontend sets `allow_synthetic: false` and shows unavailable data when a real raster is missing.
3. It derives terrain slope, roughness, relief, and candidate depressions; evaluates the configured landing footprint; and casts azimuthal terrain horizons on the spherical lunar model.
4. If `ephemeris.source` is `horizons`, the adapter requests Sun and Earth apparent observer positions from JPL. A local cache avoids repeating the same interval query. The synthetic option is explicitly marked as non-ephemeris.
5. Illumination and geometric Earth line-of-sight are evaluated from the horizon and ephemeris series. Earth visibility is not a communications link budget.
6. Results include data provenance, assumptions, warnings, limitations, and whether the input DEM was real or synthetic. The database stores completed run configuration and results.

## Visualization and sample content

The NASA SVS Moon GLB is resized and centered by the React visualization. Site markers use backend catalog coordinates transformed to model space for display only; the asset prime-meridian alignment is not verified for survey-grade overlays. Seed site attributes remain illustrative. The active frontend does not calculate suitability scores, temperatures, or rover routes.

The “Check NASA image search” control reports whether a NASA Image and Video Library query succeeds. It is a connectivity check, not an input to terrain analysis or site scoring. QuickMap, Moon Trek, and CSA links are reference links only in this version.

## Coordinate and algorithm assumptions

The app uses a spherical Moon with reference radius 1,737,400 m for its projections and great-circle estimates. Real PGDA rasters are expected in south-polar stereographic coordinates in the MOON_ME / DE421 frame. The code reads projection values from the GeoTIFF CRS and reports assumptions; verify product metadata before relying on analysis.

The crater routine is a multiscale topographic depression candidate detector, not a validated crater catalog. At each scale it compares the interior mean to eight means in a surrounding annulus. A candidate requires adequate observations in at least seven sectors, depth and depth/diameter thresholds, then undergoes local-maximum and cross-scale duplicate suppression. Missing rim sectors cannot count as enclosing terrain. Candidates inform footprint checks; they are not a scientific classification product.

## Operational dependencies

Docker uses a Node build stage in `backend/Dockerfile` to compile the frontend before copying it into the Python image. The API container requires the database and outbound internet for NASA/JPL requests. Real LOLA raster downloads are mounted through `./data:/app/data`. Environment variables are documented in `.env.example`; keep `.env` private.
