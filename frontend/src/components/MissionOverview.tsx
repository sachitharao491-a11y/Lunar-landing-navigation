import { motion } from "framer-motion";
import { Compass, Radio, Sun } from "lucide-react";

const principles = [
  { icon: Compass, title: "A demanding frontier", text: "The lunar south pole contains regions with long shadows, steep relief, and difficult access. Site selection needs traceable surface data." },
  { icon: Sun, title: "Illumination matters", text: "Sun angles and terrain horizons shape when a surface point receives direct sunlight. This app separates local terrain results from geometric sky positions." },
  { icon: Radio, title: "Earth in view", text: "Geometric visibility is a useful first check for line of sight. It is not a radio link budget, and terrain obstruction needs elevation data." },
];

export function MissionOverview() {
  return <section id="mission" className="section mission-section">
    <div className="section-heading">
      <p className="eyebrow">01 / MISSION CONTEXT</p>
      <motion.h2 initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>A map for decisions<br /><em>made in the dark.</em></motion.h2>
      <p className="section-lede">A research interface for exploring candidate locations with real ephemeris and terrain products where available. The visual model is not a survey-grade geographic overlay.</p>
    </div>
    <div className="principle-grid">{principles.map(({ icon: Icon, title, text }, i) =>
      <motion.article className="principle-card" key={title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }}>
        <span className="principle-index">0{i + 1}</span><Icon size={20} strokeWidth={1.3} /><h3>{title}</h3><p>{text}</p>
      </motion.article>)}
    </div>
  </section>;
}
