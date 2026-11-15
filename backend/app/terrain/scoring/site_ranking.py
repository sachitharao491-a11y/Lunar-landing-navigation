"""Transparent weighted site scoring with a HARD-CONSTRAINT gate.

S = sum_i w_i * score_i over available components (weights renormalised; missing components are listed).
The score is diagnostic. It can NEVER turn a failed hard constraint into an acceptable site: status is
decided by the footprint assessment first, the score only orders sites within the same status class.
Weights are demo settings (project plan), not NASA mission standards.
"""
from __future__ import annotations

import numpy as np

STATUS_ORDER = {"MEETS_CONFIGURED_CRITERIA": 0, "CONDITIONAL": 1, "UNKNOWN": 2, "REJECTED_HARD_CONSTRAINT": 3}


def _clip(x):
    return float(np.clip(x, 0.0, 100.0))


def terrain_safety_score(checks):
    ratios = [c["value"] / c["limit"] for c in checks
              if c["name"] in ("max_slope_in_footprint", "elevation_range_in_footprint") and c["value"] is not None and c["limit"]]
    if any(c["status"] == "FAIL" for c in checks):
        return 0.0
    if not ratios or any(c["status"] == "UNKNOWN" for c in checks):
        return None
    return _clip(100.0 * (1.0 - max(ratios)))


def assess(footprint, illumination, communication, quality, mc, spec, scfg):
    checks = footprint["checks"]
    comps = {
        "terrain_safety": terrain_safety_score(checks),
        "sunlight": None if illumination is None else _clip(illumination["percent_illuminated"]),
        "communication": None if communication is None else _clip(communication["visibility_percent"]),
        "roughness": None if footprint.get("roughness_p95_m") is None else _clip(100 * (1 - footprint["roughness_p95_m"] / spec.max_roughness_m)),
    }
    conf = [x for x in (quality.get("confidence_score"), None if not mc else mc.get("confidence_indicator_percent")) if x is not None]
    comps["data_confidence"] = _clip(float(np.mean(conf))) if conf else None
    w = {k: float(v) for k, v in scfg.weights.items() if k in comps}
    avail = {k: v for k, v in comps.items() if v is not None and w.get(k, 0) > 0}
    wsum = sum(w[k] for k in avail)
    score = float(sum(w[k] * avail[k] for k in avail) / wsum) if wsum else None
    missing = [k for k, v in comps.items() if v is None]
    st = footprint["footprint_status"]
    status = {"FAIL": "REJECTED_HARD_CONSTRAINT", "UNKNOWN": "UNKNOWN", "WARNING": "CONDITIONAL",
              "PASS": "MEETS_CONFIGURED_CRITERIA"}[st]
    return {
        "score": None if score is None else round(score, 1), "status": status,
        "hard_constraint_failed": st == "FAIL", "terrain_status": st, "score_complete": not missing,
        "missing_components": missing, "components": {k: None if v is None else round(v, 1) for k, v in comps.items()},
        "weights_used": {k: round(w[k] / wsum, 4) for k in avail} if wsum else {}, "weights_source": scfg.weights_source,
        "criteria_source": spec.criteria_source,
        "interpretation": ("A failed hard constraint cannot be offset by a high score." if st == "FAIL" else
                           "Score orders sites within the same status class; it is not a safety probability."),
        "disclaimer": "Research prototype; not a certified landing-safety assessment or a NASA recommendation.",
    }


def rank_sites(results):
    """Sort analysis results: status class first (eligible before rejected), then score descending."""
    def key(r):
        a = r["assessment"]
        return (STATUS_ORDER.get(a["status"], 9), -(a["score"] if a["score"] is not None else -1))
    out = sorted(results, key=key)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out
