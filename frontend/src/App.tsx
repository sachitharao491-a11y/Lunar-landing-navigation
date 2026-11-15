import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, CircleHelp } from "lucide-react";
import { Navbar } from "./components/Navbar";
import { Hero } from "./components/Hero";
import { MissionOverview } from "./components/MissionOverview";
import { SiteExplorer } from "./components/SiteExplorer";
import { ObservationDashboard } from "./components/ObservationDashboard";
import { SiteComparison } from "./components/SiteComparison";
import { TerrainPanel } from "./components/TerrainPanel";
import { DataSources } from "./components/DataSources";
import { compareObservations, getObservation, getSites } from "./services/api";
import type { Observation, ObservationLocation, Site } from "./types/api";

function utcInputNow() { return new Date().toISOString().slice(0, 16); }
function utcIso(value: string) { return new Date(`${value}:00Z`).toISOString(); }

export default function App() {
  const [sites, setSites] = useState<Site[]>([]);
  const [siteStatus, setSiteStatus] = useState<"loading" | "ready" | "error">("loading");
  const [siteError, setSiteError] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [observationTime, setObservationTime] = useState(utcInputNow);
  const [observation, setObservation] = useState<Observation | null>(null);
  const [observationStatus, setObservationStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [observationError, setObservationError] = useState("");
  const [comparison, setComparison] = useState<Observation[]>([]);
  const [comparisonStatus, setComparisonStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [comparisonError, setComparisonError] = useState("");

  useEffect(() => {
    let active = true;
    getSites().then((records) => {
      if (!active) return;
      setSites(records);
      setSiteStatus("ready");
      const candidates = records.filter((site) => site.kind === "landing");
      setSelectedId(candidates[0]?.id ?? records[0]?.id ?? null);
    }).catch((cause: Error) => {
      if (!active) return;
      setSiteError(cause.message);
      setSiteStatus("error");
    });
    return () => { active = false; };
  }, []);

  const selectedSite = useMemo(() => sites.find((site) => site.id === selectedId) ?? null, [sites, selectedId]);
  function selectSite(site: Site) {
    setSelectedId(site.id);
    setObservation(null);
    setObservationStatus("idle");
    setObservationError("");
  }
  async function requestObservation(location: ObservationLocation) {
    if (!observationTime) return;
    setObservation(null);
    setObservationError("");
    setObservationStatus("loading");
    try {
      const result = await getObservation(location, utcIso(observationTime));
      setObservation(result);
      setObservationStatus("ready");
    } catch (cause) {
      setObservationError(cause instanceof Error ? cause.message : "Observation request failed.");
      setObservationStatus("error");
    }
  }
  async function requestComparison(locations: ObservationLocation[]) {
    if (locations.length !== 2 || !observationTime) return;
    setComparison([]);
    setComparisonError("");
    setComparisonStatus("loading");
    try {
      setComparison(await compareObservations(locations, utcIso(observationTime)));
      setComparisonStatus("ready");
    } catch (cause) {
      setComparisonError(cause instanceof Error ? cause.message : "Comparison request failed.");
      setComparisonStatus("error");
    }
  }

  return <div className="app-shell">
    <Navbar />
    <main>
      <Hero sites={sites} />
      <MissionOverview />
      <SiteExplorer sites={sites} status={siteStatus} error={siteError} selected={selectedSite} onSelect={selectSite} />
      <ObservationDashboard site={selectedSite} time={observationTime} onTimeChange={(value) => { setObservationTime(value); setObservation(null); setObservationStatus("idle"); setComparison([]); setComparisonStatus("idle"); setComparisonError(""); }} observation={observation} status={observationStatus} error={observationError} onFetch={requestObservation} />
      <SiteComparison sites={sites} time={observationTime} observations={comparison} status={comparisonStatus} error={comparisonError} onCompare={requestComparison} />
      <TerrainPanel site={selectedSite} date={observationTime} />
      <DataSources />
      <section className="section about-section" id="about"><div><p className="eyebrow">ABOUT THE SYSTEM</p><h2>Exploration begins<br /><em>with evidence.</em></h2></div><div className="about-copy"><CircleHelp size={19} /><p>Lunar Landing Navigator is an educational research interface. It connects existing Python astronomy and terrain modules to a responsive React presentation layer. Measurements are shown only when returned by the backend, with method and provenance alongside them.</p><a href="/docs" target="_blank" rel="noreferrer">Inspect the API <ArrowUpRight size={14} /></a></div></section>
    </main>
    <footer className="site-footer"><a className="wordmark" href="#home"><span className="wordmark-mark">L</span><span>LUNAR<br />LANDING</span></a><span>SCIENTIFIC DATA · BACKEND OWNED</span><a href="https://svs.gsfc.nasa.gov/14959/" target="_blank" rel="noreferrer">NASA GSFC Moon model attribution ↗</a></footer>
  </div>;
}
