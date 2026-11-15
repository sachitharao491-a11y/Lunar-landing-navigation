# Originality and code-quality audit

## Scope and method

Reviewed the supplied ZIP’s source, SQL, container files, scripts, tests, front-end assets, and project documentation. The archive contains 96 entries, including Python bytecode caches. The review looked for duplicated structures, stale descriptions, missing provenance, and implementation-specific correctness risks. No AI-detection score was used. This repository has no Git history or source manifest, so authorship and exact code lineage cannot be established from the ZIP alone.

## Findings

### Provenance and possible reuse

- The astronomy module is explicitly credited in its README and integration documents as a team member’s package and is described there as unchanged. That is a documented internal reuse relationship; it is not evidence that the code was copied from an external source.
- The standalone demo repeats parts of the full app’s Three.js initialization and interaction code. It is intentionally shipped as a self-contained static demo, but edits to shared behavior can drift between the two copies. No source history was available to identify when or by whom the copies were made.
- The project bundles `frontend/assets/moon.glb`, a NASA Goddard SVS model. The existing asset README records the source and credit; the audit adds a central attribution page and an explicit non-endorsement note.
- No external source code with an uncredited license header or a recognizable pasted implementation was confirmed in this archive. Lack of a match is not proof of independent authorship. Maintain contributor records and cite any future borrowed code at the point of use.

### Maintainability and correctness

- The main front end previously combined HTML, CSS, and application logic in one dense file. They are now split into `index.html`, `styles.css`, and `app.js`, with formatting applied and the existing global Three.js loading order preserved. The standalone demo stays self-contained by design.
- The Scientific Data panel and some project documentation described resources as disconnected even though the ZIP includes a live Horizons path, an on-demand LOLA download/load path, a bundled NASA Moon model, and a NASA image-search check. The panel and root README now state the actual scope. QuickMap, Moon Trek, and CSA are labeled as external links only.
- Crater detection used the second-lowest rim-sector mean as evidence of enclosure, but did not require seven valid sector means. With two missing sectors, a missing-data edge could be sorted as high ground. The detector now requires seven measured sectors and masks unsupported centers. A focused regression test was added.
- There is meaningful domain-specific code in the lunar projection, terrain horizon, footprint evaluation, and crater candidate algorithms. These are documented as project implementations and prototype methods, not asserted to be NASA software or mission standards.
- The archive included generated `__pycache__` bytecode. It is removed from the revised package; source and tests remain.

### Documentation and attribution gaps

- The original README’s API table omitted the terrain and astronomy endpoints, and its description of NASA integrations did not match the actual code paths.
- No root license was present. A third-party dependency license does not license this project’s original code. The revised docs state that limitation and leave project licensing to the contributors/owner rather than assigning rights without evidence.
- The model had an asset-specific credit, but the project lacked a unified list distinguishing live inputs, downloadable data, bundled assets, and reference links. Added `SOURCES_AND_ATTRIBUTION.md` and `ARCHITECTURE.md`.
- Contributor roles were only noted as “Member 1/2” in source docs. Added a fill-in template; names and contribution claims are intentionally left blank for the team to complete.
- Several planning documents contain historical build notes (such as files unavailable during a prior build). They may not describe the current ZIP’s state. They should be reviewed by their authors before being treated as current validation evidence.

## Changes implemented in this audit

- Separated and formatted the primary front-end markup, styling, and classic-script application code without changing its Three.js integration model.
- Corrected the front-end resource descriptions and button label so external references and connectivity checks are not presented as data feeds.
- Rewrote the root README around the ZIP’s current implementation, sample-data boundaries, setup, APIs, and validation commands.
- Added architecture, attribution, originality-audit, contribution-template, and changelog documents.
- Corrected crater detection’s handling of missing rim sectors and added a regression test for that case.
- Removed generated Python bytecode caches from the working package copy.

## Verification run for this revision

- `python -m pytest tests astronomy/tests -q -rs`: **169 passed, 14 skipped**. All skips are opt-in live Horizons tests; one upstream AnyIO/pytest deprecation warning was emitted.
- `node --check frontend/app.js`: passed.
- `npx prettier@3.6.2 --check frontend/index.html frontend/styles.css frontend/app.js`: passed.
- Python AST parse: all 62 Python source files parsed; FastAPI app import and OpenAPI schema generation succeeded.
- `python -m pip check`: no broken installed requirements.
- Headless Chrome/Playwright loaded the page, opened the data panel, found all eight resource links, opened the explorer, selected a site, and loaded the bundled NASA model. No page JavaScript exceptions occurred. The static-only server returns an expected 404 for `/api/sites` because the backend is not running.
- ASGI requests returned HTTP 200 for `/`, `/api/analysis/defaults`, `/api/astronomy/health`, `/api/nasa/search`, and a live `/api/astronomy/v1/observation` request to JPL Horizons.
- Database-backed endpoints and real-DEM analysis were not verified: PostgreSQL/PostGIS and Docker are unavailable in this environment. The live ephemeris check covered one site/time only; it is not broad scientific validation.

## Remaining work

- Have contributors fill in `TEAM_CONTRIBUTIONS.md` and confirm the internal astronomy attribution.
- Select and add a project license only after all contributors agree to grant it.
- Decide whether to extract the shared standalone-demo globe code into a common frontend package; this was deferred to preserve the demo’s no-build, single-file usage.
- Validate with downloaded PGDA rasters and a real Horizons request before presenting any real-data analysis result. Synthetic tests do not establish real-data accuracy.
