import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Activity, ArrowUpRight, Radio, Sun } from "lucide-react";
import type { Observation, ObservationLocation, Site } from "../types/api";

const value = (number: number | null, digits = 2) => number === null ? "Unavailable" : number.toFixed(digits);
const stateLabel = (state: boolean | null) => state === null ? "Not returned" : state ? "Above geometric horizon" : "Below geometric horizon";
const utcLabel = (iso: string) => new Date(iso).toISOString().replace("T", " ").replace("Z", " UTC");

function Metric({ label, value: metric, unit, detail }: { label: string; value: string; unit?: string; detail?: string }) {
  return <div className="metric"><span>{label}</span><strong>{metric}{metric !== "Unavailable" && unit ? <small> {unit}</small> : null}</strong>{detail && <p>{detail}</p>}</div>;
}

function CelestialDetails({ body }: { body: Observation["sun"] }) {
  return <details className="interval-details celestial-details"><summary>Additional Horizons values</summary><div className="celestial-detail-grid">
    <Metric label="Right ascension" value={value(body.ra_deg)} unit="°" /><Metric label="Declination" value={value(body.dec_deg)} unit="°" />
    <Metric label="Range rate" value={value(body.range_rate_km_s, 4)} unit="km/s" /><Metric label="Phase angle" value={value(body.phase_angle_deg)} unit="°" />
    <Metric label="Illuminated fraction" value={value(body.illuminated_fraction)} unit="fraction" />
  </div></details>;
}

export function ObservationDashboard({ site, time, onTimeChange, observation, status, error, onFetch }: {
  site: Site | null; time: string; onTimeChange: (value: string) => void; observation: Observation | null;
  status: "idle" | "loading" | "ready" | "error"; error: string; onFetch: (location: ObservationLocation) => void;
}) {
  const [latitude, setLatitude] = useState(site ? String(site.lat) : "");
  const [longitude, setLongitude] = useState(site ? String(site.lon) : "");
  const [coordinateError, setCoordinateError] = useState("");
  const [coordinatesChanged, setCoordinatesChanged] = useState(false);
  useEffect(() => {
    if (!site) return;
    setLatitude(String(site.lat));
    setLongitude(String(site.lon));
    setCoordinateError("");
    setCoordinatesChanged(false);
  }, [site?.id]);
  function requestAtCoordinates() {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!latitude.trim() || !longitude.trim() || !Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 360) {
      setCoordinateError("Enter latitude from −90 to 90 and east longitude from −180 to 360 degrees.");
      return;
    }
    setCoordinateError("");
    setCoordinatesChanged(false);
    const matchesCatalog = site && lat === site.lat && lon === site.lon;
    onFetch({ site_name: matchesCatalog ? site.name : "Custom lunar coordinates", latitude_deg: lat, longitude_deg_east: lon, altitude_km: 0 });
  }
  return <section id="science" className="section science-section">
    <div className="section-topline"><p className="eyebrow">03 / LIVE ASTRONOMY</p><span className="section-count">JPL HORIZONS · API</span></div>
    <div className="science-intro"><div><h2>The sky, from<br /><em>this location.</em></h2><p>Request an observation from the Python service. Sun and Earth positions come from the existing Horizons integration; no browser-side ephemeris is calculated.</p></div>
      <div className="observation-controls"><label htmlFor="observation-time">Observation time <span>UTC</span></label><input id="observation-time" type="datetime-local" value={time} onChange={(event) => onTimeChange(event.target.value)} />
        <div className="coordinate-inputs"><label htmlFor="observation-latitude">Latitude <span>degrees, north positive</span></label><input id="observation-latitude" aria-label="Observation latitude" type="number" min="-90" max="90" step="any" value={latitude} onChange={(event) => { setLatitude(event.target.value); setCoordinatesChanged(true); }} />
          <label htmlFor="observation-longitude">Longitude <span>degrees, east positive</span></label><input id="observation-longitude" aria-label="Observation east longitude" type="number" min="-180" max="360" step="any" value={longitude} onChange={(event) => { setLongitude(event.target.value); setCoordinatesChanged(true); }} /></div>
        {coordinateError && <p className="field-hint error-text" role="alert">{coordinateError}</p>}
        <button className="button-light" onClick={requestAtCoordinates} disabled={!time || status === "loading"}>{status === "loading" ? <><span className="spinner dark" />Querying Horizons…</> : <>Request observation <ArrowUpRight size={15} /></>}</button>
        <p className="field-hint">Coordinates default to the selected catalog site and can be edited. Horizons receives the entered coordinates directly.</p>
      </div>
    </div>
    {status === "error" && <div className="error-banner" role="alert"><strong>Observation unavailable</strong><span>{error}</span></div>}
    {status === "idle" && <div className="empty-science"><Activity size={18} /><span>{coordinatesChanged ? "Coordinates changed. Request a new backend observation to update these results." : "No observation requested. Results will appear here after the backend responds."}</span></div>}
    {observation && !coordinatesChanged && <motion.div className="observation-results" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <div className="result-provenance"><span className="live-dot" /> JPL HORIZONS · AIRLESS APPARENT OBSERVER VALUES <span className="result-time">{observation.site.name} · {observation.site.latitude_deg}° lat · {observation.site.longitude_deg_east}° east · altitude {observation.site.altitude_km} km · {utcLabel(observation.datetime_utc)}</span></div>
      <div className="body-results">
        <article className="body-card"><div className="body-title"><span className="body-symbol sun-symbol"><Sun size={17} /></span><div><span>CELESTIAL BODY</span><h3>Sun</h3></div><span className="visibility-state">{stateLabel(observation.sun.is_above_horizon)}</span></div>
          <div className="metric-grid"><Metric label="Azimuth" value={value(observation.sun.azimuth_deg)} unit="°" /><Metric label="Elevation" value={value(observation.sun.elevation_deg)} unit="°" /><Metric label="Range" value={value(observation.sun.range_km, 0)} unit="km" /></div>
          <div className="irradiance-note"><strong>Solar irradiance · simplified estimate</strong><div className="irradiance-values"><span>{value(observation.solar_irradiance.direct_normal_w_m2, 1)} <small>W/m² direct normal</small></span><span>{value(observation.solar_irradiance.horizontal_surface_w_m2, 1)} <small>W/m² horizontal</small></span></div><p>{observation.solar_irradiance.limitations}</p><a href={observation.solar_irradiance.reference_source_url} target="_blank" rel="noreferrer">{observation.solar_irradiance.reference_source} ↗</a></div>
        </article>
        <article className="body-card"><div className="body-title"><span className="body-symbol earth-symbol"><Radio size={17} /></span><div><span>CELESTIAL BODY</span><h3>Earth</h3></div><span className="visibility-state">{stateLabel(observation.earth.is_above_horizon)}</span></div>
          <div className="metric-grid"><Metric label="Azimuth" value={value(observation.earth.azimuth_deg)} unit="°" /><Metric label="Elevation" value={value(observation.earth.elevation_deg)} unit="°" /><Metric label="Range" value={value(observation.earth.range_km, 0)} unit="km" /></div>
          <div className="communication-note"><span className="note-label">GEOMETRIC VISIBILITY</span><strong>{observation.earth_visibility.geometric_line_of_sight === null ? "Unavailable" : observation.earth_visibility.geometric_line_of_sight ? "Line of sight" : "Below local geometric horizon"}</strong><p>Terrain-aware visibility: not returned by this single-epoch endpoint.</p><p>Radio link: {observation.earth_visibility.radio_link_assessment}. {observation.earth_visibility.radio_link_note}</p></div>
        </article>
      </div>
      <CelestialDetails body={observation.sun} /><CelestialDetails body={observation.earth} />
      <p className="science-footnote">{observation.data_source} · {observation.position_type}; visibility: {observation.visibility_scope}. Displayed values and units are taken from the backend response.</p>
    </motion.div>}
  </section>;
}
