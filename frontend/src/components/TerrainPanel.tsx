import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Database, Layers3, MapPinned } from "lucide-react";
import { analyzeTerrain, getLolaTerrainPreview } from "../services/api";
import type { Site, TerrainAnalysis, TerrainCatalog } from "../types/api";
import { getTerrainCatalog } from "../services/api";

function backendDate(value: string) { return new Date(`${value}:00Z`).toISOString(); }

function BackendTerrainMap({ data }: { data: NonNullable<TerrainAnalysis["maps"]> }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context) return;
    const height = data.slope_deg.length;
    const width = data.slope_deg[0]?.length ?? 0;
    if (!width || !height) return;
    canvas.current!.width = width;
    canvas.current!.height = height;
    const pixels = context.createImageData(width, height);
    for (let row = 0; row < height; row += 1) for (let column = 0; column < width; column += 1) {
      const offset = (row * width + column) * 4;
      const slope = data.slope_deg[row][column];
      const hazard = data.hazard_class[row]?.[column];
      if (!Number.isFinite(slope) || hazard === 3) {
        pixels.data.set([105, 108, 110, 255], offset);
        continue;
      }
      const intensity = Math.max(0, Math.min(1, slope / 30));
      pixels.data.set([Math.round(45 + 210 * intensity), Math.round(145 - 90 * intensity), Math.round(220 - 175 * intensity), 255], offset);
    }
    context.putImageData(pixels, 0, 0);
  }, [data]);
  return <figure className="backend-terrain-map"><canvas ref={canvas} aria-label="Backend LOLA slope and hazard map" /><figcaption>Backend LOLA slope map · visualization scale 0–30° · gray indicates unknown hazard pixels · source window {data.extent_m[0].toFixed(0)} × {data.extent_m[1].toFixed(0)} m at {data.pixel_m.toFixed(1)} m/pixel</figcaption></figure>;
}

export function TerrainPanel({ site, date }: { site: Site | null; date: string }) {
  const [catalog, setCatalog] = useState<TerrainCatalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [result, setResult] = useState<TerrainAnalysis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [latitude, setLatitude] = useState(site ? String(site.lat) : "");
  const [longitude, setLongitude] = useState(site ? String(site.lon) : "");
  const [preview, setPreview] = useState<{ url: string; source: string; product: string; resolutionM: number; coordinates: string; displayNote: string } | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [previewBusy, setPreviewBusy] = useState(false);
  useEffect(() => { getTerrainCatalog().then(setCatalog).catch((cause: Error) => setCatalogError(cause.message)); }, []);
  useEffect(() => {
    if (!site) return;
    setLatitude(String(site.lat));
    setLongitude(String(site.lon));
    setResult(null);
    setPreview(null);
  }, [site?.id]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  const data = useMemo(() => catalog?.sites.find((row) => row.site_id === site?.id), [catalog, site]);
  const elevation = result?.terrain as Record<string, unknown> | undefined;
  const point = result?.analysis_point as Record<string, unknown> | undefined;
  const illumination = result?.illumination;
  const communication = result?.communication;
  const field = (key: string, digits = 2) => {
    const value = elevation?.[key];
    return typeof value === "number" ? value.toFixed(digits) : "Unavailable";
  };

  async function runPreview() {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!latitude.trim() || !longitude.trim() || !Number.isFinite(lat) || lat < -90 || lat > -80 || !Number.isFinite(lon) || lon < -180 || lon > 360) {
      setPreviewError("The NASA regional LOLA hillshade covers 80–90°S. Enter latitude from −90 to −80 and east longitude from −180 to 360 degrees.");
      return;
    }
    setPreviewBusy(true); setPreviewError(""); setPreview(null);
    try {
      const response = await getLolaTerrainPreview(lat, lon);
      setPreview({ ...response, url: URL.createObjectURL(response.blob) });
    } catch (cause) {
      setPreviewError(cause instanceof Error ? cause.message : "LOLA image request failed.");
    } finally { setPreviewBusy(false); }
  }

  async function runAnalysis() {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!site || !data?.elevation_present || !Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 360) {
      setError("Enter valid lunar coordinates and select a site with a locally installed LOLA analysis raster.");
      return;
    }
    setBusy(true); setError(""); setResult(null);
    try { setResult(await analyzeTerrain(site.id, backendDate(date), { lat, lon })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Terrain analysis failed."); }
    finally { setBusy(false); }
  }

  return <section className="section terrain-section" id="terrain">
    <div className="section-topline"><p className="eyebrow">05 / SURFACE ANALYSIS</p><span className="section-count">NASA PGDA / LRO LOLA</span></div>
    <div className="terrain-layout"><div><h2>Read the<br /><em>terrain itself.</em></h2><p>Request a regional LOLA hillshade centered on your entered coordinates. The backend reads the NASA cloud-optimized raster and returns an image; it does not create replacement terrain.</p>
      <div className="terrain-source-card"><Database size={18} /><div><strong>NASA PGDA / LRO LOLA</strong><span>80–90°S, 20 m/pixel hillshade · remote COG preview</span></div></div>
      <a className="terrain-product-link" href="https://pgda.gsfc.nasa.gov/products/90" target="_blank" rel="noreferrer">View the NASA PGDA product record ↗</a>
    </div><div className="terrain-result-card">
      <div className="terrain-card-head"><MapPinned size={17} /><span>HILLSHADE CENTER</span><strong>{site?.name ?? "Entered coordinates"}</strong></div>
      <div className="terrain-coordinates"><label htmlFor="terrain-latitude">Latitude <span>80–90°S coverage</span></label><input id="terrain-latitude" aria-label="Terrain latitude" type="number" min="-90" max="-80" step="any" value={latitude} onChange={(event) => { setLatitude(event.target.value); setPreview(null); setResult(null); }} />
        <label htmlFor="terrain-longitude">Longitude <span>degrees east-positive</span></label><input id="terrain-longitude" aria-label="Terrain east longitude" type="number" min="-180" max="360" step="any" value={longitude} onChange={(event) => { setLongitude(event.target.value); setPreview(null); setResult(null); }} /></div>
      <button className="button-light terrain-run" disabled={previewBusy} onClick={runPreview}>{previewBusy ? <><span className="spinner dark" />Requesting NASA LOLA image…</> : "Load LOLA hillshade image"}</button>
      {previewError && <div className="error-banner small" role="alert"><AlertCircle size={16} />{previewError}</div>}
      {preview && <figure className="lola-preview"><img src={preview.url} alt={`NASA LOLA hillshade centered at ${preview.coordinates}`} /><figcaption>{preview.source} · {preview.product} · {preview.resolutionM} m/pixel · {preview.coordinates} · {preview.displayNote}</figcaption></figure>}
      <details className="local-analysis"><summary><Layers3 size={15} /> Detailed terrain analysis from installed site DEM</summary>
        {catalogError ? <div className="error-banner small" role="alert"><AlertCircle size={16} />{catalogError}</div> : null}
        {!catalog && !catalogError && <p className="subtle-note">Checking local elevation products…</p>}
        {catalog && !data && <p className="subtle-note">No registered local 5 m DEM is linked to this catalog site.</p>}
        {data && !data.elevation_present && <p className="subtle-note">No local 5 m LOLA raster is installed for this site. The remote 20 m hillshade preview above remains available.</p>}
        {data?.elevation_present && <button className="button-light terrain-run" disabled={busy || !date} onClick={runAnalysis}>{busy ? <><span className="spinner dark" />Running terrain analysis…</> : "Analyze this coordinate in the site DEM"}</button>}
        {error && <div className="error-banner small" role="alert">{error}</div>}
        {result && <div className="terrain-results" aria-live="polite"><div className="terrain-result-status"><span>BACKEND ASSESSMENT</span><strong>{result.assessment.status.replaceAll("_", " ")}</strong></div>
          <div className="metric-grid"><div className="metric"><span>Mean slope</span><strong>{field("mean_slope_deg")}<small> °</small></strong></div><div className="metric"><span>95th percentile slope</span><strong>{field("p95_slope_deg")}<small> °</small></strong></div><div className="metric"><span>Analysis latitude</span><strong>{typeof point?.lat_deg === "number" ? point.lat_deg.toFixed(4) : "Unavailable"}<small> °</small></strong></div></div>
          {result.maps && <BackendTerrainMap data={result.maps} />}
          {illumination && <div className="backend-window"><span className="note-label">TERRAIN-AWARE SOLAR ILLUMINATION</span><div className="window-values"><strong>{illumination.percent_illuminated === null ? "Unavailable" : `${illumination.percent_illuminated.toFixed(1)}%`}<small> of selected period</small></strong><span>{typeof illumination.sunlight_hours === "number" ? `${illumination.sunlight_hours.toFixed(2)} sunlight hours` : "Sunlight duration unavailable"}</span><span>{typeof illumination.terrain_blocked_hours === "number" ? `${illumination.terrain_blocked_hours.toFixed(2)} h blocked by terrain` : "Terrain blockage unavailable"}</span></div></div>}
          {communication && <div className="backend-window"><span className="note-label">TERRAIN-AWARE EARTH LINE OF SIGHT</span><div className="window-values"><strong>{communication.visibility_percent === null ? "Unavailable" : `${communication.visibility_percent.toFixed(1)}%`}<small> of selected period</small></strong><span>{typeof communication.visibility_hours === "number" ? `${communication.visibility_hours.toFixed(2)} visible hours` : "Visibility duration unavailable"}</span><span>Terrain obstruction: {communication.terrain_obstruction_status ?? "Not returned"}</span></div></div>}
          <p className="science-footnote">Source: {String(result.dataset.source ?? "LOLA")} · {String(result.dataset.resolution_m ?? "—")} m/pixel · {result.provenance.algorithm_version}. Generated: {result.provenance.generated_at ?? "not provided"}.</p>
        </div>}
      </details>
    </div></div>
  </section>;
}

