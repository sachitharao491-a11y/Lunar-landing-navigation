import { motion } from "framer-motion";
import { MapPin, MousePointer2 } from "lucide-react";
import { MoonScene } from "./MoonScene";
import type { Site } from "../types/api";

function coordinate(lat: number, lon: number) {
  const latitude = `${Math.abs(lat).toFixed(3)}° ${lat < 0 ? "S" : "N"}`;
  const longitude = `${Math.abs(lon).toFixed(3)}° ${lon < 0 ? "W" : "E"}`;
  return `${latitude} · ${longitude}`;
}

export function SiteExplorer({ sites, status, error, selected, onSelect }: {
  sites: Site[]; status: "loading" | "ready" | "error"; error: string; selected: Site | null;
  onSelect: (site: Site) => void;
}) {
  return <section id="sites" className="section explorer-section">
    <div className="section-topline"><p className="eyebrow">02 / LANDING SITE EXPLORER</p><span className="section-count">{status === "ready" ? `${sites.length.toString().padStart(2, "0")} CATALOG RECORDS` : "BACKEND CATALOG"}</span></div>
    <div className="explorer-heading"><h2>Choose a point<br /><em>on the surface.</em></h2><p>Locations and coordinates are loaded from the project API. The Moon model is a visual asset; its geographic overlay is approximate and not survey-grade.</p></div>
    <div className="explorer-layout">
      <div className="explorer-view">
        {sites.length ? <MoonScene sites={sites} selectedId={selected?.id} onSelect={onSelect} interactive /> : <div className="empty-panel">{status === "loading" ? <><span className="spinner" />Loading site catalog…</> : <><strong>Site catalog unavailable</strong><span>{error || "No backend site records were returned."}</span></>}</div>}
        <div className="model-caption"><span><span className="caption-dot" /> SELECT A BACKEND SITE</span><span>NASA GSFC MOON MODEL · VISUAL ONLY</span></div>
        <div className="model-help"><MousePointer2 size={13} /> Drag to rotate · scroll to zoom · select a marker</div>
      </div>
      <aside className="site-panel">
        <div className="panel-kicker"><MapPin size={14} /> SITE CATALOG <span>{sites.length ? sites.length.toString().padStart(2, "0") : "—"}</span></div>
        {selected ? <div className="selected-site">
          <span className="site-kind">{selected.kind.toUpperCase()} SITE · API RECORD</span>
          <h3>{selected.name}</h3>
          <p className="site-coords">{coordinate(selected.lat, selected.lon)}</p>
          <div className="site-meta"><span>Latitude</span><strong>{selected.lat.toFixed(5)}°</strong><span>Longitude east</span><strong>{selected.lon.toFixed(5)}°</strong></div>
          <div className="notice"><strong>Catalog provenance</strong><p>{selected.source}</p><p>Seed records may be illustrative. These coordinates and attributes are not presented as a validated landing recommendation.</p></div>
          {selected.note && <p className="site-note">{selected.note}</p>}
        </div> : <div className="empty-panel compact">Select a site after the API catalog loads.</div>}
        <div className="site-list-heading"><span>AVAILABLE LOCATIONS</span><span>SELECT TO EXPLORE</span></div>
        <div className="site-list" aria-label="Landing site list">
          {sites.map((site) => <motion.div layout key={site.id} className={`site-row ${selected?.id === site.id ? "site-row-active" : ""}`}>
            <button className="site-row-main" onClick={() => onSelect(site)} aria-pressed={selected?.id === site.id}>
              <span className="site-row-name">{site.name}</span><span className="site-row-coords">{coordinate(site.lat, site.lon)}</span>
            </button>
          </motion.div>)}
        </div>
      </aside>
    </div>
  </section>;
}
