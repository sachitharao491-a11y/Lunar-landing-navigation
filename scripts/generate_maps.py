#!/usr/bin/env python3
"""Generate elevation / slope / hazard / horizon figures for one site (real DEM if present, else labeled synthetic).

  python scripts/generate_maps.py --site Site04 --out docs/img/site04.png
  python scripts/generate_maps.py --synthetic --out docs/img/synthetic_demo.png
"""
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from app.terrain.config import AnalysisConfig
from app.terrain.ingestion.dem_loader import DatasetNotAvailable, load_bundle
from app.terrain.ingestion.synthetic import make_synthetic_bundle
from app.terrain.pipeline import run_analysis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site"); ap.add_argument("--synthetic", action="store_true"); ap.add_argument("--out", default="terrain_maps.png")
    a = ap.parse_args()
    try:
        b = make_synthetic_bundle() if a.synthetic or not a.site else load_bundle(a.site)
    except DatasetNotAvailable as e:
        sys.exit(f"{e}\nUse --synthetic for a labeled demo.")
    cfg = AnalysisConfig(); cfg.auto_select_point = True; cfg.uncertainty.runs = 0
    r = run_analysis(b, cfg, sky=None, include_maps=True)
    m = r["maps"]
    fig, ax = plt.subplots(1, 4, figsize=(19, 4.6))
    ext = [0, m["extent_m"][0], m["extent_m"][1], 0]
    im = ax[0].imshow(np.array(m["elevation_m"], float), cmap="terrain", extent=ext); fig.colorbar(im, ax=ax[0], label="m"); ax[0].set_title("Elevation")
    im = ax[1].imshow(np.array(m["slope_deg"], float), cmap="inferno", vmin=0, vmax=30, extent=ext); fig.colorbar(im, ax=ax[1], label="deg"); ax[1].set_title("Slope")
    cols = ["#2ecc71", "#f39c12", "#e74c3c", "#95a5a6"]
    from matplotlib.colors import ListedColormap
    ax[2].imshow(np.array(m["hazard_class"]), cmap=ListedColormap(cols), vmin=0, vmax=3, extent=ext); ax[2].set_title("Footprint hazard (green PASS / orange WARN / red FAIL / grey UNKNOWN)", fontsize=8)
    for k in (0, 1, 2):
        ax[k].plot(m["point_rc"][1] * m["pixel_m"], m["point_rc"][0] * m["pixel_m"], "c+", ms=14)
    h = r["horizon"]
    ax[3].fill_between(h["azimuth_deg"], h["sun_horizon_deg"], -5, color="#556", label="terrain horizon"); ax[3].plot(h["azimuth_deg"], h["antenna_horizon_deg"], "c", lw=1, label="antenna height")
    ax[3].set_xlim(0, 360); ax[3].set_xlabel("azimuth (deg, 0=N)"); ax[3].set_ylabel("elevation (deg)"); ax[3].set_title("Horizon mask"); ax[3].legend(fontsize=8)
    tag = "REAL NASA LOLA" if r["dataset"]["real_data"] else "SYNTHETIC (not lunar data)"
    fig.suptitle(f"{r['site_name']} | {tag} | status: {r['assessment']['status']} | criteria: {r['assessment']['criteria_source']}", fontsize=10)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    fig.tight_layout(); fig.savefig(a.out, dpi=110); print("wrote", a.out)


if __name__ == "__main__":
    main()
