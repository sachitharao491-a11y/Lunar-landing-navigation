#!/usr/bin/env python3
"""Validate the engine against NASA reference products for one downloaded site.

 1. Slope: own slope vs NASA's slope GeoTIFF (slp) over a window -> bias/RMSE/correlation.
 2. Illumination (optional): simulated % at the analysis point vs an LROC WAC illumination map GeoTIFF
    (percent map; historical period, coarser resolution, so a plausibility check, not a target).

  python scripts/validate_against_nasa.py --site Site04
  python scripts/validate_against_nasa.py --site Site04 --lroc data/raw/lroc/WAC_POLE_ILL_PCT_SOUTH.tif --observations sky.json
Records errors and differences instead of hiding them; writes docs/validation_<site>.json.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.terrain.config import AnalysisConfig
from app.terrain.ephemeris.sky import from_observation_dicts
from app.terrain.ingestion.dem_loader import load_bundle
from app.terrain.pipeline import clean, run_analysis
from app.terrain.validation.reference import illumination_vs_reference, sample_lroc_percent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True); ap.add_argument("--lroc"); ap.add_argument("--observations", help="Member 1 rows JSON (list)")
    ap.add_argument("--data-dir"); ap.add_argument("--method", default="gradient", choices=["gradient", "horn"])
    a = ap.parse_args()
    b = load_bundle(a.site, a.data_dir)
    cfg = AnalysisConfig(); cfg.auto_select_point = True; cfg.uncertainty.runs = 0
    sky = from_observation_dicts(json.load(open(a.observations))) if a.observations else None
    r = run_analysis(b, cfg, sky=sky, include_maps=False)
    out = {"site": a.site, "dataset": r["dataset"]["files"], "slope_vs_nasa": r["validation"]["slope_vs_nasa_product"], "point": r["analysis_point"]}
    if b.nasa_slope is None:
        out["slope_vs_nasa"] = {"status": "NASA slope file (slp) not found; download it with scripts/download_data.py --products slp"}
    if a.lroc and r["illumination"]:
        ref = sample_lroc_percent(a.lroc, r["analysis_point"]["lat_deg"], r["analysis_point"]["lon_deg_east"])
        out["illumination_vs_lroc"] = illumination_vs_reference(r["illumination"]["percent_illuminated"], ref)
    elif a.lroc:
        out["illumination_vs_lroc"] = {"status": "need --observations (Sun series) to simulate illumination"}
    os.makedirs("docs", exist_ok=True)
    path = f"docs/validation_{a.site}.json"
    json.dump(clean(out), open(path, "w"), indent=1)
    print(json.dumps(clean(out), indent=1)); print("wrote", path)


if __name__ == "__main__":
    main()
