import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowUpRight, GitCompareArrows } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Observation, ObservationLocation, Site } from "../types/api";

type Entry = { choice: string; latitude: string; longitude: string };
const emptyEntry = (): Entry => ({ choice: "custom", latitude: "", longitude: "" });
const utcLabel = (iso: string) => new Date(iso).toISOString().replace("T", " ").replace("Z", " UTC");
const display = (value: number | null, digits = 2) => value === null ? "Unavailable" : value.toFixed(digits);
const angle = (value: number | null) => value === null ? "Unavailable" : `${value.toFixed(2)}°`;

export function SiteComparison({ sites, time, observations, status, error, onCompare }: {
  sites: Site[]; time: string; observations: Observation[]; status: "idle" | "loading" | "ready" | "error";
  error: string; onCompare: (locations: ObservationLocation[]) => void;
}) {
  const [a, setA] = useState<Entry>(emptyEntry);
  const [b, setB] = useState<Entry>(emptyEntry);
  const [coordinateError, setCoordinateError] = useState("");
  const [inputsChanged, setInputsChanged] = useState(false);
  useEffect(() => {
    if (!sites.length) return;
    const available = sites.filter((site) => site.kind === "landing");
    const first = available[0] ?? sites[0];
    const second = available.find((site) => site.id !== first.id) ?? sites.find((site) => site.id !== first.id);
    if (first) setA({ choice: String(first.id), latitude: String(first.lat), longitude: String(first.lon) });
    if (second) setB({ choice: String(second.id), latitude: String(second.lat), longitude: String(second.lon) });
  }, [sites]);

  function selectSite(which: "a" | "b", choice: string) {
    const site = sites.find((candidate) => String(candidate.id) === choice);
    const update = which === "a" ? setA : setB;
    update(site ? { choice, latitude: String(site.lat), longitude: String(site.lon) } : { ...(which === "a" ? a : b), choice: "custom" });
    setCoordinateError("");
    setInputsChanged(true);
  }

  function compare() {
    const entries = [a, b];
    const labels = ["Site A", "Site B"];
    const locations: ObservationLocation[] = [];
    for (let index = 0; index < entries.length; index += 1) {
      const entry = entries[index];
      const latitude = Number(entry.latitude);
      const longitude = Number(entry.longitude);
      if (!entry.latitude.trim() || !entry.longitude.trim() || !Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 360) {
        setCoordinateError(`${labels[index]}: enter latitude from −90 to 90 and east longitude from −180 to 360 degrees.`);
        return;
      }
      const site = sites.find((candidate) => String(candidate.id) === entry.choice);
      locations.push({ site_name: site?.name ?? `${labels[index]} (custom)`, latitude_deg: latitude, longitude_deg_east: longitude, altitude_km: 0 });
    }
    setCoordinateError("");
    setInputsChanged(false);
    onCompare(locations);
  }

  const chartData = observations.map((item) => ({ site: item.site.name, sunElevation: item.sun.elevation_deg, earthElevation: item.earth.elevation_deg }));
  function updateEntry(which: "a" | "b", key: "latitude" | "longitude", value: string) {
    const update = which === "a" ? setA : setB;
    update((entry) => ({ ...entry, choice: "custom", [key]: value }));
    setInputsChanged(true);
  }

  return <section className="section comparison-section" id="comparison">
    <div className="section-topline"><p className="eyebrow">04 / SITE COMPARISON</p><span className="section-count">SAME UTC INSTANT · BACKEND RESULTS</span></div>
    <div className="comparison-intro"><div><h2>Same sky.<br /><em>Different horizons.</em></h2><p>Choose two catalog locations or enter coordinates for either site. Both are sent together to the backend Horizons batch endpoint at the same observation time shown above.</p></div>
      <button className="button-outline" disabled={status === "loading" || !time} onClick={compare}>{status === "loading" ? <><span className="spinner" />Comparing…</> : <><GitCompareArrows size={16} /> Compare these sites <ArrowUpRight size={14} /></>}</button>
    </div>
    <div className="comparison-inputs">
      {([["a", "Site A", a], ["b", "Site B", b]] as const).map(([which, label, entry]) => <div className="comparison-input-card" key={which}>
        <span className="note-label">{label}</span>
        <label htmlFor={`comparison-${which}-choice`}>Location source</label>
        <select id={`comparison-${which}-choice`} value={entry.choice} onChange={(event) => selectSite(which, event.target.value)}>
          {sites.map((site) => <option key={site.id} value={String(site.id)}>{site.name}</option>)}
          <option value="custom">Enter custom coordinates</option>
        </select>
        <div className="coordinate-inputs"><label htmlFor={`comparison-${which}-lat`}>Latitude <span>north positive</span></label><input id={`comparison-${which}-lat`} aria-label={`${label} latitude`} type="number" min="-90" max="90" step="any" value={entry.latitude} onChange={(event) => updateEntry(which, "latitude", event.target.value)} />
          <label htmlFor={`comparison-${which}-lon`}>Longitude <span>east positive</span></label><input id={`comparison-${which}-lon`} aria-label={`${label} east longitude`} type="number" min="-180" max="360" step="any" value={entry.longitude} onChange={(event) => updateEntry(which, "longitude", event.target.value)} /></div>
      </div>)}
    </div>
    {coordinateError && <div className="error-banner" role="alert">{coordinateError}</div>}
    {error && <div className="error-banner" role="alert"><strong>Comparison unavailable</strong><span>{error}</span></div>}
    {observations.length > 0 && !inputsChanged ? <motion.div className="comparison-results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="chart-card"><div className="chart-heading"><div><span className="note-label">BACKEND OBSERVATION</span><h3>Sun and Earth elevation</h3></div><span>{utcLabel(observations[0].datetime_utc)}</span></div>
        <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: 2 }}>
          <CartesianGrid stroke="#282b2d" vertical={false} /><XAxis dataKey="site" tick={{ fill: "#a6a6a6", fontSize: 11 }} axisLine={{ stroke: "#333" }} tickLine={false} /><YAxis domain={[-90, 90]} tick={{ fill: "#85898b", fontSize: 10 }} tickFormatter={(v) => `${v}°`} axisLine={false} tickLine={false} width={42} />
          <Tooltip contentStyle={{ background: "#151719", border: "1px solid #383b3d", borderRadius: 2, color: "#f5f5f5" }} formatter={(v) => [v === null ? "Unavailable" : `${v}°`, "Elevation"]} />
          <Legend wrapperStyle={{ color: "#a6a6a6", fontSize: 11 }} /><Bar dataKey="sunElevation" name="Sun elevation" fill="#e6e1d8" radius={[2, 2, 0, 0]} /><Bar dataKey="earthElevation" name="Earth elevation" fill="#858b91" radius={[2, 2, 0, 0]} />
        </BarChart></ResponsiveContainer></div>
      </div>
      <div className="comparison-table-wrap"><table className="data-table"><thead><tr><th>Site</th><th>Sun azimuth</th><th>Sun elevation</th><th>Earth azimuth</th><th>Earth elevation</th><th>Earth geometric LOS</th></tr></thead>
        <tbody>{observations.map((item) => <tr key={`${item.site.name}-${item.datetime_utc}`}><td>{item.site.name}</td><td>{angle(item.sun.azimuth_deg)}</td><td>{angle(item.sun.elevation_deg)}</td><td>{angle(item.earth.azimuth_deg)}</td><td>{angle(item.earth.elevation_deg)}</td><td>{item.earth_visibility.geometric_line_of_sight === null ? "Unavailable" : item.earth_visibility.geometric_line_of_sight ? "Visible" : "Below horizon"}</td></tr>)}</tbody>
      </table></div>
      {observations.map((item) => <details className="interval-details celestial-details" key={`${item.site.name}-details`}><summary>{item.site.name} · additional Horizons values</summary><div className="celestial-detail-grid"><span>Sun RA / Dec: {display(item.sun.ra_deg)}° / {display(item.sun.dec_deg)}°</span><span>Sun range: {display(item.sun.range_km, 0)} km</span><span>Earth RA / Dec: {display(item.earth.ra_deg)}° / {display(item.earth.dec_deg)}°</span><span>Earth range: {display(item.earth.range_km, 0)} km</span><span>Sun phase / illumination: {display(item.sun.phase_angle_deg)}° / {display(item.sun.illuminated_fraction)}</span><span>Earth phase / illumination: {display(item.earth.phase_angle_deg)}° / {display(item.earth.illuminated_fraction)}</span></div></details>)}
      <p className="science-footnote">Comparison values are returned by JPL Horizons via the backend. Geometric visibility excludes local terrain obstruction; the frontend assigns no suitability score.</p>
    </motion.div> : (status === "idle" || inputsChanged) && <div className="empty-science"><GitCompareArrows size={18} /><span>Choose both locations and request a comparison to see the backend results side by side.</span></div>}
  </section>;
}
