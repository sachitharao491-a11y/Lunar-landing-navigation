"""Configuration for the terrain engine. Every threshold is explicit and echoed in results.

Nothing here is a NASA mission standard. LanderSpec values are DEMO DEFAULTS and must be
replaced with the real lander specification before any result is interpreted.
"""
from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

ALGORITHM_VERSION = "terrain-engine/1.0.0"


@dataclass
class LanderSpec:
    footprint_radius_m: float = 15.0        # landing footprint (incl. legs)
    clearance_margin_m: float = 10.0        # extra ring around the footprint
    max_slope_deg: float = 10.0             # HARD limit inside footprint
    max_relief_m: float = 2.0               # HARD limit: max-min elevation across footprint
    max_roughness_m: float = 0.5            # HARD limit: p95 detrended RMS roughness
    roughness_window_m: float = 15.0
    obstacle_height_m: float = 1.0          # positive relief that counts as an obstacle
    crater_fail_depth_m: float = 2.0        # crater inside footprint deeper than this fails
    warn_fraction: float = 0.8              # WARNING when value > warn_fraction * limit
    unknown_if_invalid_fraction: float = 0.10
    uncertainty_sigma: float = 2.0          # k in (slope + k*sigma) > limit -> WARNING
    criteria_source: str = "DEMO_DEFAULTS"  # set to e.g. "lander_spec_v3" when real values are used


@dataclass
class SimulationConfig:
    start_utc: Optional[datetime] = None
    end_utc: Optional[datetime] = None
    step_minutes: int = 10                  # Horizons resolution is 1 minute
    refine_s: float = 10.0                  # rise/set refinement tolerance
    sun_height_m: float = 1.0               # observer height for sunlight rays
    antenna_height_m: float = 2.0           # observer height for Earth line of sight
    earth_min_elevation_deg: float = 0.0    # antenna mask (configuration, not link budget)
    min_lit_fraction: float = 0.0           # sun disk fraction that counts as lit (> value)

    def resolved(self) -> "SimulationConfig":
        s = self.start_utc or datetime.now(timezone.utc).replace(second=0, microsecond=0)
        e = self.end_utc or (s + timedelta(days=30))
        return dataclasses.replace(self, start_utc=s, end_utc=e)


@dataclass
class ScoringConfig:
    # Proposed demo weights from the project plan; NOT NASA standards. Normalised before use.
    weights: dict = field(default_factory=lambda: {
        "terrain_safety": 0.35, "sunlight": 0.25, "communication": 0.20,
        "roughness": 0.10, "data_confidence": 0.10})
    weights_source: str = "DEMO_DEFAULTS (proposed in project plan; not NASA mission standards)"
    ref_sigma_z_m: float = 1.0              # z-uncertainty at which the confidence component reaches 0
    ref_sigma_slope_deg: float = 3.0
    target_measured_fraction: float = 0.10  # PGDA: ~90% of 5 m pixels are interpolated


@dataclass
class UncertaintyConfig:
    runs: int = 30                          # 0 disables Monte Carlo
    seed: int = 0
    corr_length_m: float = 50.0             # spatial correlation of synthetic perturbations
    include_visibility: bool = False        # re-run horizon ray casting per realization (slow)
    max_visibility_runs: int = 20


@dataclass
class AnalysisConfig:
    lander: LanderSpec = field(default_factory=LanderSpec)
    sim: SimulationConfig = field(default_factory=SimulationConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    uncertainty: UncertaintyConfig = field(default_factory=UncertaintyConfig)
    window_radius_m: float = 1500.0         # tile window for derivative maps / craters
    n_azimuths: int = 720
    auto_select_point: bool = False
    normal_window_px: int = 3

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("start_utc", "end_utc"):
            v = d["sim"].get(k)
            d["sim"][k] = v.isoformat() if v else None
        return d


def _coerce(cls, data):
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in (data or {}).items() if k in names})


def config_from_dict(d: Optional[dict]) -> AnalysisConfig:
    """Build an AnalysisConfig from a plain dict, ignoring unknown keys."""
    d = dict(d or {})
    sim = dict(d.pop("sim", {}) or {})
    for k in ("start_utc", "end_utc"):
        if isinstance(sim.get(k), str):
            sim[k] = datetime.fromisoformat(sim[k].replace("Z", "+00:00"))
    cfg = _coerce(AnalysisConfig, {k: v for k, v in d.items()
                                   if k not in ("lander", "scoring", "uncertainty")})
    cfg.lander = _coerce(LanderSpec, d.get("lander"))
    cfg.sim = _coerce(SimulationConfig, sim)
    cfg.scoring = _coerce(ScoringConfig, d.get("scoring"))
    cfg.uncertainty = _coerce(UncertaintyConfig, d.get("uncertainty"))
    return cfg
