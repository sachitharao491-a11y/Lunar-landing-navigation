import { motion } from "framer-motion";
import { ArrowDown, ArrowUpRight } from "lucide-react";
import { MoonScene } from "./MoonScene";
import type { Site } from "../types/api";

export function Hero({ sites }: { sites: Site[] }) {
  return <section id="home" className="hero-section">
    <div className="hero-copy">
      <motion.p className="eyebrow" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
        <span className="eyebrow-line" /> LUNAR SOUTH POLE · MISSION SYSTEMS
      </motion.p>
      <motion.h1 initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.85, delay: 0.12 }}>
        LUNAR<br /><em>LANDING</em>
      </motion.h1>
      <motion.p className="hero-subtitle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}>Explore the Lunar South Pole</motion.p>
      <motion.p className="hero-description" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.45 }}>
        Discover potential landing locations through scientific analysis of solar illumination, Earth visibility and lunar surface conditions. Navigate the Moon with reliable astronomical data and clear provenance.
      </motion.p>
      <motion.a className="primary-link" href="#mission" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.55 }}>
        Explore mission <ArrowUpRight size={16} strokeWidth={1.5} />
      </motion.a>
      <a className="scroll-cue" href="#mission"><ArrowDown size={14} /> SCROLL TO EXPLORE</a>
    </div>
    <div className="hero-visual" aria-label="NASA Goddard lunar model, shown as a visual asset">
      <div className="orbit orbit-one" /><div className="orbit orbit-two" />
      <MoonScene sites={sites} autoRotate className="hero-moon" />
      <div className="hero-coordinate"><span>01 / MOON</span><span>VISUAL MODEL · NASA GSFC</span></div>
    </div>
    <div className="hero-footer"><span>MISSION OVERVIEW</span><span className="footer-rule" /><span>01 — 06</span></div>
    <span className="hero-side-note">SELENOGRAPHIC EXPLORATION · 2026</span>
  </section>;
}
