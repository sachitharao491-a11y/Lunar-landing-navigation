# Lunar Landing Navigator

An educational application for lunar south-pole exploration. The active frontend is React and TypeScript; FastAPI and the existing Python astronomy and terrain modules own scientific data access and calculations.

## What is real and what is illustrative

- The globe uses the bundled NASA Goddard SVS Moon 3D model, derived from LRO imagery and topography.
- Terrain analysis can read NASA GSFC PGDA / LRO LOLA 5 m/pixel GeoTIFF products after you download them with `scripts/download_data.py`. If a product is missing, the API can use labeled synthetic terrain for demonstration; it is not lunar data.
- Terrain analysis can query JPL Horizons for Sun and Earth observer ephemerides. This requires network access and a running backend. Choose synthetic tracks or no ephemeris when appropriate.
- The NASA Image and Video Library connection button performs a live search check. Its results do not populate site attributes or analyses.
- Landing-site values in the database and front-end demo (including sunlight, ice, hazard, and science scores) are hand-entered illustrative values. They are not live measurements or NASA recommendations.
- QuickMap, Moon Trek, and the CSA Moon Exploration portal are external learning links. This version does not query their services. Diviner and the PDS Geosciences Node are not ingested by the app.

See [SOURCES_AND_ATTRIBUTION.md](SOURCES_AND_ATTRIBUTION.md) for dataset, service, asset, and library references; [ARCHITECTURE.md](ARCHITECTURE.md) for the data flow; and [ORIGINALITY_AUDIT.md](ORIGINALITY_AUDIT.md) for audit findings and changes.

## Features

- Cinematic, responsive React interface with a visual-only NASA Goddard Moon model.
- Backend-backed site catalog, Horizons Sun/Earth observations, and multi-site comparison.
- LOLA terrain analysis and terrain-aware windows when real elevation rasters are installed; the frontend shows unavailable states instead of synthetic results.
- Existing FastAPI accounts, site, terrain, astronomy, saved-plan, and NASA search endpoints.

The source frontend is in `frontend/src/`; the prior static app is preserved in `frontend/index.html`, `frontend/app.js`, and `frontend/styles.css`. See [frontend/README.md](frontend/README.md) for development and API ownership details.

The terrain analysis is a research prototype, not a certified landing-safety assessment. Its default lander criteria and scoring weights are demonstration values. See the limitations in [docs/TERRAIN_ENGINE.md](docs/TERRAIN_ENGINE.md).

## Set up Supabase

The project uses Supabase Postgres for its database. Run the schema in a new or empty Supabase project before starting the API:

1. Create a Supabase project and open **Database → Extensions**. Enable **postgis** in the `extensions` schema.
2. Open **SQL Editor** and create a query. Copy all of `db/schema.sql` into it and run it.
3. Create another SQL Editor query, copy all of `db/seed.sql`, and run it.
4. Create one more query, copy all of `db/002_terrain.sql`, and run it.

Run these files in order, once, in a fresh project. The schema creates the app tables and custom lunar coordinate reference system; the seed adds illustrative sample sites. The terrain SQL also enables row-level security without public policies. The backend connects with the private database role, so it can access the tables while Supabase Data API roles cannot.

## Run with Docker Desktop

Docker builds the React app and runs it with the API. Supabase hosts the database; Docker does not create a local database container.

1. In Supabase Dashboard, click **Connect**, select **Session pooler**, and copy the connection string. Use the provided host, port, and username as-is. The app uses `asyncpg` with a persistent connection pool, so choose session mode on port `5432`, not transaction mode on port `6543`. [Supabase connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
2. In the project folder, create your environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Edit `.env`. Replace `DATABASE_URL` with the full Supabase session-pooler URL, including `?sslmode=require`. URL-encode special characters in the database password. Set `JWT_SECRET` to a long random secret; you can generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Start Docker Desktop and wait until it reports that the engine is running.
5. From the project folder, build and start the app:

   ```powershell
   docker compose up --build
   ```

6. Open [http://localhost:8000](http://localhost:8000). The API docs are at [http://localhost:8000/docs](http://localhost:8000/docs), and the database connectivity check is [http://localhost:8000/api/health](http://localhost:8000/api/health).

Leave that PowerShell window open while using the app. Press **Ctrl+C** to stop it; `docker compose down` also stops the API container. Neither command deletes or resets your Supabase database. For startup output, run `docker compose logs -f api` in another PowerShell window.

### Run the backend without Docker

You still need the Supabase SQL setup above. Install Python, then in PowerShell from the repository folder:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Fill in `DATABASE_URL` and `JWT_SECRET` in the repository’s `.env`, then set them in the current PowerShell session (or use your preferred environment-file loader) and start the server:

```powershell
$env:DATABASE_URL = "paste-your-supabase-session-pooler-url"
$env:JWT_SECRET = "paste-your-long-random-secret"
uvicorn app.main:app --reload
```

For frontend development with hot reload, start the backend as above and then run `npm ci --legacy-peer-deps` and `npm run dev` from `frontend/`; Vite proxies API requests to port 8000. For a browser-only legacy demonstration without the backend, use [standalone-demo/README.txt](standalone-demo/README.txt).

## Real LOLA terrain data

The source products are large and are not bundled in the ZIP. From the project root:

```sh
python scripts/download_data.py --list
python scripts/download_data.py --site Site04
```

The files are saved below `data/raw/` by default. Set `TERRAIN_DATA_DIR` to choose another location. With Docker, `./data` is mounted into the API container. The analysis dataset endpoint reports which sites have elevation files available. Review the source product notes before interpreting a result; PGDA reports that many 5 m pixels are interpolated.

The React interface also has a coordinate-centered south-pole hillshade preview. Its backend endpoint reads a small window from NASA PGDA's 20 m/pixel cloud-optimized LOLA hillshade for 80–90°S, so a multi-gigabyte local download is not required for the image preview. This is a visualization product, separate from detailed terrain analysis, which still uses installed site-specific 5 m rasters.

## API overview

| Path | Purpose |
|---|---|
| `GET /api/health` | Database connectivity check |
| `GET /api/sites` | Site list, optional kind and bounding-box filters |
| `GET /api/sites/{id}` | Site detail and illustrative suitability score |
| `POST /api/score` | Rank sites using client-supplied weights |
| `POST /api/route` | Great-circle route duration estimate |
| `GET /api/datasets` | Seeded catalog of external resources and status labels |
| `GET /api/nasa/search` | Cached NASA Image and Video Library search proxy |
| `GET /api/analysis/lola/preview?latitude_deg=…&longitude_deg_east=…` | NASA PGDA LOLA hillshade window for coordinates from 80–90°S |
| `/api/analysis/*` | Terrain datasets, analysis, comparison, validation, and saved runs |
| `/api/astronomy/*` | Horizons-backed observation and visibility service |
| `/api/auth/*`, `/api/favorites/*`, `/api/plans/*` | Optional account and saved-plan endpoints |

## Configuration and security

See `.env.example` for the Supabase database URL, JWT, CORS, and frontend settings. Keep `.env` private. Do not expose a deployment using the development JWT secret. Use HTTPS and restrict `CORS_ORIGINS` to the actual frontend origin.

## Verification

Build the frontend from `frontend/` with `npm ci --legacy-peer-deps`, `npm run test`, and `npm run build`. Run the available backend checks from the project root:

```sh
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
python -m pytest astronomy/tests
```

Some astronomy tests use saved Horizons responses; explicitly marked live tests require external access. Real-DEM validation additionally requires downloading the PGDA files and running `scripts/validate_against_nasa.py`.

## Project license

The provided ZIP did not include a project-level license. Until the project owner selects and adds one, the original project code has no blanket reuse grant. Third-party assets and libraries retain their own terms; see [SOURCES_AND_ATTRIBUTION.md](SOURCES_AND_ATTRIBUTION.md). NASA attribution does not imply NASA endorsement.
