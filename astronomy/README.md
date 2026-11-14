# Astronomy Module — Member 1

## Purpose

Determine the positions (azimuth, elevation, distance) of the **Sun** and **Earth**
as observed from a selected lunar south-pole landing site at a specified UTC date/time.

## File Structure

```
astronomy/
│
├── __init__.py               # Package metadata, version, coordinate-convention docs
│
├── api/                      # Network layer — talks to JPL Horizons
│   ├── __init__.py
│   ├── horizons_client.py    # Build, send, and parse Horizons API queries
│   └── config.py             # API base URL, default parameters, timeouts
│
├── calculations/             # Pure-math / geometry layer — no network calls
│   ├── __init__.py
│   ├── geometry.py           # Angle utils, angular separation, shadows, incidence
│   ├── solar.py              # Sun analysis, time comparison, site comparison
│   ├── earth_visibility.py   # Earth analysis, comm windows, phase names
│   └── visibility.py         # Disk-aware visibility, rise/set detection, sunlit hours
│
├── models/                   # Data structures shared across the module
│   ├── __init__.py
│   └── landing_site.py       # LandingSite, CelestialResult, QueryParams, etc.
│
├── validation/               # Compare our results against independent sources
│   ├── __init__.py
│   └── scientific_validation.py
│
├── web/                      # FastAPI integration for team backend
│   ├── __init__.py
│   └── app.py                # Health, single-observation, and bounded batch endpoints
│
├── tests/                    # Automated tests
│   ├── __init__.py
│   ├── test_horizons_client.py
│   ├── test_calculations.py
│   └── test_models.py
│
├── data/
│   └── cache/                # Optional response caching (gitignored)
│
├── docs/
│   └── PHASE1_HORIZONS_INVESTIGATION.md   # ← You are here
│
├── requirements.txt          # Python dependencies for this module
└── README.md                 # This file
```

## Technology Stack

| Tool | Role |
|------|------|
| Python 3.10+ | Language |
| FastAPI | REST endpoints (integration phase) |
| httpx / requests | HTTP client for Horizons API |
| NumPy | Numerical calculations |
| SpiceyPy | SPICE kernels (if/when needed) |

## FastAPI integration (Phase 6)

The web layer is an adapter around the existing Horizons client. Its endpoints
validate input and return typed JSON; astronomy queries and calculations stay
in the Python backend. The batch route accepts up to ten site/time requests and
queries them sequentially.

Start from the repository root (install `astronomy/requirements.txt` first):

```powershell
uvicorn astronomy.web.app:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive OpenAPI page.

Endpoints:

- `GET /health` — local liveness check; does not contact Horizons.
- `POST /v1/observation` — one lunar site and UTC instant.
- `POST /v1/observations/batch` — up to ten independent site/time requests.

Example request body:

```json
{
  "site_name": "Shackleton Rim",
  "latitude_deg": -89.68,
  "longitude_deg_east": 129.0,
  "altitude_km": 0.0,
  "datetime_utc": "2026-03-01T12:00:00Z"
}
```

Latitude and longitude use Horizons lunar geodetic conventions; longitude is
east-positive and altitude is kilometres. `datetime_utc` must include a UTC
offset (`Z` is recommended); accepted offsets are normalized to UTC. Invalid
input returns HTTP 422, an unreachable Horizons service returns 503, and an
upstream or parse failure returns 502. A batch request fails with the mapped
error if any included observation fails. Returned positions are Horizons
airless apparent observer quantities; visibility scope is explicitly
geometric and excludes local terrain.

## Coordinate Conventions

| Property | Convention |
|----------|-----------|
| Longitude | East-positive (IAU / Horizons default for Moon) |
| Latitude | Planetocentric (selenocentric) |
| Azimuth | 0° = North, clockwise through East |
| Elevation | Positive above horizon, negative below |
| Time | UTC input; internally converted to TDB where required |

## Development Phases

1. ✅ **PHASE 1** — Investigate JPL Horizons API query configuration
2. ✅ **PHASE 2** — Implement Python API client with error handling
3. ✅ **PHASE 3** — Calculate Sun/Earth azimuth & elevation
4. ✅ **PHASE 4** — Geometric visibility determination
5. 🟡 **PHASE 5** — Live Horizons comparison and three plausibility runs completed; matched SPICE cross-check remains pending (see [PHASE5_VALIDATION.md](docs/PHASE5_VALIDATION.md))
6. ✅ **PHASE 6** — FastAPI endpoints added for single and bounded batch queries

