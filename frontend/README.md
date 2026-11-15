# React frontend

The active interface is built with React, TypeScript, Vite, Tailwind CSS, React Three Fiber, Drei, Framer Motion, Lucide, and Recharts. The older static implementation remains at `index.html`, `app.js`, and `styles.css` for preservation; FastAPI serves the compiled React bundle from `dist/` when present.

## Development

Start the FastAPI backend on port 8000, then from this directory:

```powershell
npm ci --legacy-peer-deps
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` only when the API is hosted on a different origin; configure the backend CORS allowlist for that origin.

## Production build

```powershell
npm ci --legacy-peer-deps
npm run build
```

Vite writes the bundle to `dist/`. The backend and Docker image serve that built directory. The original NASA Moon GLB is preserved, while the active visual export is simplified to about 4.6 MB (from roughly 51.4 MB). Coordinate markers are a visualization transform only; the model's prime meridian is not verified for survey-grade geographic overlays.

## Scientific data ownership

`src/services/api.ts` is the only frontend API boundary. The site catalog, Horizons observations, terrain products, and data-source status are fetched from FastAPI. Single observations and two-site comparisons accept editable coordinates and use the existing single/batch Horizons routes. The LOLA preview uses a backend endpoint that reads a coordinate window from NASA's 20 m/pixel south-pole cloud-optimized hillshade; it covers 80–90°S and needs backend outbound network access. Detailed terrain analysis remains tied to local 5 m site DEMs and sends `allow_synthetic: false` with the entered coordinate. Runtime shape checks reject malformed responses; no API failure is replaced with sample science.

The Horizons single and batch routes return airless apparent sky directions. Their Earth visibility is geometric; it does not model local terrain or a radio link. The separate terrain analysis API can compute terrain-aware sunlight and geometric Earth visibility when real DEM data are installed. The current seed site attributes are illustrative and are not treated as measurements in this frontend.
