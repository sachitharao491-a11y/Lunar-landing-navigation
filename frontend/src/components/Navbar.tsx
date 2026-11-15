import { useState } from "react";
import { Menu, X } from "lucide-react";

const links = [
  ["Mission", "#mission"],
  ["Landing sites", "#sites"],
  ["Scientific data", "#sources"],
  ["About", "#about"],
];

export function Navbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="site-header">
      <a className="wordmark" href="#home" aria-label="Lunar Landing home">
        <span className="wordmark-mark">L</span><span>LUNAR<br />LANDING</span>
      </a>
      <nav className={open ? "nav-links nav-open" : "nav-links"} aria-label="Main navigation">
        <a href="#home" onClick={() => setOpen(false)}>Home</a>
        {links.map(([label, href]) => <a key={href} href={href} onClick={() => setOpen(false)}>{label}</a>)}
      </nav>
      <a className="nav-cta" href="#sites">Open explorer <span aria-hidden="true">↗</span></a>
      <button className="menu-toggle" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>
      {open && <nav className="menu-overlay" aria-label="Expanded navigation">
        <a href="#home" onClick={() => setOpen(false)}>Home</a>
        {links.map(([label, href]) => <a key={href} href={href} onClick={() => setOpen(false)}>{label}</a>)}
      </nav>}
    </header>
  );
}
