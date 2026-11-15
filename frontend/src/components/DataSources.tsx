import { useEffect, useState } from "react";
import { ArrowUpRight, Database, Globe2, RadioTower } from "lucide-react";
import { getDataSources, getTerrainCatalog } from "../services/api";
import type { DataSource, TerrainCatalog } from "../types/api";

const iconFor = (name: string) => name.toLowerCase().includes("horizons") ? RadioTower : name.toLowerCase().includes("lola") ? Database : Globe2;

export function DataSources() {
  const [sources, setSources] = useState<DataSource[] | null>(null);
  const [terrain, setTerrain] = useState<TerrainCatalog | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([getDataSources(), getTerrainCatalog()]).then(([data, catalog]) => { setSources(data); setTerrain(catalog); }).catch((cause: Error) => setError(cause.message));
  }, []);
  const realDemCount = terrain?.sites.filter((site) => site.elevation_present).length ?? 0;
  return <section className="section sources-section" id="sources">
    <div className="section-topline"><p className="eyebrow">06 / DATA &amp; PROVENANCE</p><span className="section-count">SOURCE STATUS FROM API</span></div>
    <div className="sources-heading"><h2>Know where<br /><em>the signal begins.</em></h2><p>Source records and local elevation availability are retrieved from the backend. A linked source does not imply that its data are ingested.</p></div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {!sources && !error && <div className="empty-science"><span className="spinner" />Loading source records…</div>}
    {sources && <div className="source-list">{sources.map((source, index) => {
      const Icon = iconFor(source.name);
      const status = source.name.toLowerCase().includes("lola") && terrain ? `Remote 20 m preview · ${realDemCount} local 5 m DEM${realDemCount === 1 ? "" : "s"}` : source.status.replaceAll("-", " ");
      return <article className="source-row" key={source.name}><span className="source-index">0{index + 1}</span><Icon size={17} strokeWidth={1.4} /><div className="source-copy"><h3>{source.name}</h3><p>{source.description}</p></div><span className="source-status">{status}</span>{source.url && <a href={source.url} target="_blank" rel="noreferrer" aria-label={`Open ${source.name} source`}><ArrowUpRight size={15} /></a>}</article>;
    })}</div>}
    <div className="source-note"><span className="live-dot" /><p>JPL Horizons observations provide airless apparent Sun and Earth directions. The remote LOLA hillshade preview covers 80–90°S; detailed terrain analysis requires installed site DEMs. LROC, SPICE and Diviner products are not otherwise ingested by this application.</p></div>
  </section>;
}
