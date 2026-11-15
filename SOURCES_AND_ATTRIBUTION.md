# Sources, data, and attribution

This file records what the project uses, what it only links to, and where attribution or license information comes from. No external resource is presented as an app data feed unless an implementation path exists in this ZIP.

## Data, models, and services

| Source | Project use | Attribution / reference |
|---|---|---|
| NASA GSFC Scientific Visualization Studio, Moon 3D Models | `frontend/assets/moon.glb` is bundled and loaded by both the full app and standalone demo. It is an LRO-derived visualization asset, not a source for the database’s site scores. | Credit NASA Goddard Space Flight Center; data provider Ernie Wright (USRA). See the [NASA SVS model page](https://svs.gsfc.nasa.gov/14959/) and the asset-specific [README](frontend/assets/README.md). |
| NASA GSFC PGDA, High-Resolution LOLA Topography for Lunar South Pole Sites | `scripts/download_data.py` can download 5 m/pixel products. The terrain loader reads local files under `data/raw/`; the ZIP does not bundle the large DEM products. | Product page: [PGDA product 78](https://pgda.gsfc.nasa.gov/products/78). The page describes LRO-LOLA products, product layers, sites, frame, and interpolation. See Barker et al., [“Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions”](https://ntrs.nasa.gov/api/citations/20205009660/downloads/Mike%20Barker_%20Paper_%20Improved%20Lola.pdf), for product uncertainty and illumination context. Cite the actual product files and this paper when publishing derived results. |
| NASA LCROSS | The Cabeus sample-site note summarizes the mission result; its associated site scores remain illustrative. | [NASA LCROSS mission page](https://science.nasa.gov/mission/lcross/) and Colaprete et al., [“Detection of Water in the LCROSS Ejecta Plume”](https://doi.org/10.1126/science.1186986), *Science* 330 (2010), 463–468. |
| NASA/JPL Horizons | The astronomy module queries Horizons for apparent observer positions. Terrain analysis calls the same module for Sun and Earth time series when the `horizons` source is selected. | [Horizons system](https://ssd.jpl.nasa.gov/horizons/), [API documentation](https://ssd-api.jpl.nasa.gov/doc/horizons.html), and the project’s query conventions in `backend/astronomy/docs/PHASE1_HORIZONS_INVESTIGATION.md`. |
| NASA Image and Video Library | `/api/nasa/search` proxies image searches. The front-end button checks this endpoint and reports results; returned items do not supply terrain, site rankings, or science values. | [NASA Images](https://images.nasa.gov/) and [NASA API catalog](https://api.nasa.gov/). |
| NASA Moon Trek | Link only in this build. No Moon Trek tile request is made by the app. | [Moon Trek](https://trek.nasa.gov/moon/). The portal describes its own map layers and tools. |
| LROC QuickMap (Arizona State University) | Link only. No QuickMap service or data endpoint is queried by this build. | [LROC QuickMap](https://quickmap.lroc.asu.edu/). |
| Canadian Space Agency | Link only; the app does not ingest CSA mission data. | [CSA Moon Exploration](https://www.asc-csa.gc.ca/eng/astronomy/moon-exploration/). |
| LRO Diviner | Mentioned as a possible source in project notes. No Diviner product is downloaded or read by this build. | [Diviner Lunar Radiometer](https://diviner.ucla.edu/). |
| NASA PDS Geosciences Node | No PDS data are fetched by this build. The LOLA downloader targets the PGDA product URLs above. | [PDS Geosciences Node](https://pds-geosciences.wustl.edu/). |

The database seed explicitly labels landing-site attributes as approximate illustrative samples. Historical facts in descriptions (for example, LCROSS detecting water-bearing material in ejecta) should be tied to a mission or peer-reviewed source before being reused in a scientific report; they do not turn the associated sample scores into measured data.

## Algorithms and provenance

The crater/depression candidate routine in `backend/app/terrain/hazards/crater_detection.py`, spherical polar stereographic conversions, horizon ray casting, and safety scoring are project implementations documented in [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/TERRAIN_ENGINE.md](docs/TERRAIN_ENGINE.md). They should not be described as NASA software or as validated landing criteria. The detector returns candidates, not a crater database. The default limits and weights are demonstration settings.

Terrain results should cite the PGDA source product, downloaded product filenames, file hashes recorded by the loader, analysis version, and input configuration. The engine’s Monte Carlo perturbations are synthetic correlated fields based on available elevation uncertainty; they are not the PGDA DEM clones.

## Software and asset licensing

- The main page loads Three.js `r128` and its GLTFLoader from public CDNs. Three.js is distributed under the MIT License; see the [upstream license](https://github.com/mrdoob/three.js/blob/r128/LICENSE). Preserve the upstream notice if the library is vendored.
- Python runtime and development dependencies are listed in `backend/requirements.txt`, `backend/requirements-dev.txt`, and `backend/astronomy/requirements.txt`: [FastAPI](https://github.com/fastapi/fastapi), [Uvicorn](https://github.com/encode/uvicorn), [asyncpg](https://github.com/MagicStack/asyncpg), [HTTPX](https://github.com/encode/httpx), [PyJWT](https://github.com/jpadilla/pyjwt), [Pydantic](https://github.com/pydantic/pydantic), [NumPy](https://github.com/numpy/numpy), [SciPy](https://github.com/scipy/scipy), [Rasterio](https://github.com/rasterio/rasterio), [pyproj](https://github.com/pyproj4/pyproj), and [pytest](https://github.com/pytest-dev/pytest). Review each project's license files for the exact installed versions when creating a redistributable release; the requirements use version ranges, not a lockfile.
- PostgreSQL/PostGIS is supplied through the external [`postgis/postgis` container image](https://github.com/postgis/docker-postgis). Consult its upstream project notices for the exact image tag.
- `moon.glb` is a redistributed NASA SVS asset. Keep the credit above and review NASA’s [Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/). NASA insignia and identifiers are not included as project branding. The app must not imply NASA endorsement.
- No root project license was present in the supplied ZIP. This audit does not assume ownership or assign a new license to the original team code. The project owner should select a project license and confirm that all contributors can grant it before publishing source for reuse.

## Team-supplied code

The astronomy package is identified in its README and integration docs as Member 1’s contribution and is described as vendored unchanged. The terrain engine is attributed to Member 2 in its package and docs. Preserve those authorship statements and have contributors complete [TEAM_CONTRIBUTIONS.md](TEAM_CONTRIBUTIONS.md). This is team provenance, not evidence of external copying.
