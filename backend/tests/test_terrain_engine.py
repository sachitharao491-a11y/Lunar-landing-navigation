"""Terrain engine tests: every scenario from the Member 2 plan plus integration with Member 1's types.

Run:  cd backend && pytest tests/        (or: python tests/run_all.py when pytest is not installed)
"""
import json, os, sys, tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import _shim  # noqa: F401,E402
import numpy as np  # noqa: E402

from app.terrain.config import AnalysisConfig, LanderSpec, SimulationConfig, config_from_dict  # noqa: E402
from app.terrain.geometry.coordinates import PolarStereoGrid, azel_to_enu, enu_to_azel  # noqa: E402
from app.terrain.geometry.horizon import horizon_profile, interp_horizon  # noqa: E402
from app.terrain.geometry.surface_normals import surface_normal_enu  # noqa: E402
from app.terrain.hazards.crater_detection import detect_craters  # noqa: E402
from app.terrain.hazards.safety_assessment import combine, evaluate_point, terrain_layers  # noqa: E402
from app.terrain.ingestion.quality_control import assess_quality  # noqa: E402
from app.terrain.ingestion.synthetic import make_synthetic_bundle  # noqa: E402
from app.terrain.surface.derivatives import roughness_rms, slope_deg  # noqa: E402
from app.terrain.communication.earth_visibility import analyze_earth_visibility  # noqa: E402
from app.terrain.ephemeris.sky import SkyDataError, SkySeries, from_observation_dicts, synthetic_sky  # noqa: E402
from app.terrain.illumination.sun_visibility import analyze_illumination  # noqa: E402
from app.terrain.illumination.windows import build_intervals  # noqa: E402
from app.terrain.pipeline import clean, run_analysis  # noqa: E402
from app.terrain.scoring.site_ranking import assess, rank_sites  # noqa: E402
from app.terrain.validation.reference import compare_arrays  # noqa: E402
from app.terrain.validation.uncertainty import monte_carlo, perturbation_field  # noqa: E402

T0 = datetime(2030, 1, 1, tzinfo=timezone.utc)
AZ = np.arange(0, 360, 0.5)
FLAT = {"azimuth_deg": AZ, "elevation_deg": np.full(AZ.size, -0.001)}
UP = np.array([0.0, 0.0, 1.0])
SIM = SimulationConfig(refine_s=1.0)


def mk_sky(sun_az, sun_el, earth_az, earth_el, n=145, step=600.0):
    t = np.arange(n) * step
    f = lambda x: np.full(n, float(x)) if np.isscalar(x) else x
    return SkySeries(T0, t, {"sun": f(sun_az), "earth": f(earth_az)}, {"sun": f(sun_el), "earth": f(earth_el)},
                     {"sun": np.full(n, 1.496e8), "earth": np.full(n, 384400.0)})


# ---------------- coordinates ----------------
def test_polar_stereo_roundtrip_and_distance():
    g = PolarStereoGrid((5, 0, -1000, 0, -5, 1000), (400, 400))
    x, y = g.lonlat_to_xy(-89.7, 45.0)
    lat, lon = g.xy_to_lonlat(x, y)
    assert abs(lat + 89.7) < 1e-9 and abs(lon - 45.0) < 1e-9
    assert abs(np.hypot(x, y) - 1737400 * np.radians(0.3)) < 0.1      # arc length near the pole


def test_azel_enu_roundtrip():
    az, el = enu_to_azel(azel_to_enu(123.0, 17.0))
    assert abs(az - 123.0) < 1e-9 and abs(el - 17.0) < 1e-9


# ---------------- terrain derivatives (spec test table) ----------------
def test_flat_terrain_zero_slope():
    assert np.nanmax(slope_deg(np.full((60, 60), 100.0), 5, 5)) == 0.0


def test_constant_surface_zero_roughness():
    r = roughness_rms(np.full((60, 60), 7.0), 5)
    assert np.nanmax(r) == 0.0 and np.isnan(r[0, 0])            # border windows are NaN, never fake zeros


def test_known_plane_slope_and_detrended_roughness():
    z = np.tan(np.radians(10)) * np.arange(60)[None, :] * 5.0 + np.zeros((60, 1))
    s = slope_deg(z, 5, 5)[5:-5, 5:-5]
    assert abs(s.mean() - 10.0) < 1e-6
    assert np.nanmax(roughness_rms(z, 5)[5:-5, 5:-5]) < 1e-5           # plane removed
    assert np.nanmax(roughness_rms(z, 5, detrend=False)[5:-5, 5:-5]) > 0.5


def test_steep_hill_raises_slope_and_blocks_sun():
    b = make_synthetic_bundle(size=400, craters=False, ridge=False, roughness_m=0.0)
    b.elev[:] = 0.0
    b.elev[0:2, :] = 50.0                                               # 50 m wall, 1000 m north of centre
    lat, lon = b.grid.rowcol_to_lonlat(200, 200)
    hp = horizon_profile(b.grid, b.elev, float(lat), float(lon), 0.0, n_az=360)
    assert abs(hp["elevation_deg"].max() - np.degrees(np.arctan(50 / 1000))) < 0.05   # known answer 2.862 deg
    assert hp["elevation_deg"].max() > 2.0
    assert abs(np.nanmax(slope_deg(b.elev, 5, 5)) - np.degrees(np.arctan(25 / 5))) < 0.01   # central difference over a 50 m step


def test_flat_sphere_horizon_dips_below_zero():
    b = make_synthetic_bundle(size=300, craters=False, ridge=False)
    b.elev[:] = 0.0
    lat, lon = b.grid.rowcol_to_lonlat(150, 150)
    hp = horizon_profile(b.grid, b.elev, float(lat), float(lon), 0.0, n_az=36)
    assert hp["elevation_deg"].max() <= 0.0                              # curvature: nothing rises above the horizon


def test_crater_detected_and_no_false_positives():
    spec = LanderSpec()
    b = make_synthetic_bundle(size=500, seed=7)
    L = terrain_layers(b.elev, b.grid, spec, b.slope_err)
    cr = detect_craters(b.elev, 5.0, L["slope"], b.grid)
    pos = {(c["row"], c["col"]) for c in cr}
    assert any(abs(r - 400) < 8 and abs(c - 331) < 8 for r, c in pos)    # 9 m deep crater
    assert any(abs(r - 300) < 8 and abs(c - 110) < 8 for r, c in pos)    # 5 m deep crater
    for kw in (dict(craters=False), dict(craters=False, ridge=False)):    # ridge-only / plain terrain
        b2 = make_synthetic_bundle(size=500, seed=11, **kw)
        L2 = terrain_layers(b2.elev, b2.grid, spec)
        assert detect_craters(b2.elev, 5.0, L2["slope"], b2.grid) == []


def test_crater_detector_does_not_count_missing_rim_sectors_as_enclosure():
    elev = np.full((101, 101), 100.0)
    yy, xx = np.mgrid[:101, :101]
    radius = np.hypot(xx - 50, yy - 50)
    elev[radius <= 2.0] = 97.0
    elev[(radius > 2.0) & (radius <= 4.5)] = 102.0

    # Remove two adjacent sectors from the candidate crater's rim. The remaining
    # observations must not make the missing arc look like an enclosing wall.
    angle = (np.arctan2(yy - 50, xx - 50) + np.pi) / (2 * np.pi) * 8
    missing = (radius > 3.0) & (radius <= 4.5) & (angle < 2.0)
    elev[missing] = np.nan

    assert detect_craters(elev, 5.0, radii_m=(15,), min_depth_m=1.0) == []


# ---------------- hazards ----------------
def test_footprint_crater_floor_vs_wall():
    spec = LanderSpec()
    b = make_synthetic_bundle(size=500, seed=7)
    L = terrain_layers(b.elev, b.grid, spec, b.slope_err)
    cr = detect_craters(b.elev, 5.0, L["slope"], b.grid)
    assert evaluate_point(b.elev, L, (250, 250), spec, cr, b.count)["footprint_status"] == "PASS"
    wall = evaluate_point(b.elev, L, (402, 357), spec, cr, b.count)
    assert wall["footprint_status"] == "FAIL"


def test_status_precedence():
    assert combine(["PASS", "WARNING", "UNKNOWN"]) == "UNKNOWN"
    assert combine(["PASS", "UNKNOWN", "FAIL"]) == "FAIL"
    assert combine(["PASS", "WARNING"]) == "WARNING"


def test_missing_pixels_give_quality_warning_and_unknown():
    spec = LanderSpec()
    b = make_synthetic_bundle(size=300, craters=False, ridge=False)
    z = b.elev.copy()
    z[140:160, 140:160] = np.nan
    q = assess_quality(z, b.count, b.z_err, b.slope_err)
    assert q["missing_fraction"] > 0 and any("missing" in w for w in q["warnings"])
    L = terrain_layers(z, b.grid, spec, b.slope_err)
    r = evaluate_point(z, L, (150, 150), spec, [], b.count)
    assert r["footprint_status"] == "UNKNOWN"                           # insufficient data, not PASS


def test_higher_uncertainty_lowers_confidence():
    b = make_synthetic_bundle(size=300)
    lo = assess_quality(b.elev, b.count, np.full(b.elev.shape, 0.2), b.slope_err)["confidence_score"]
    hi = assess_quality(b.elev, b.count, np.full(b.elev.shape, 0.9), b.slope_err)["confidence_score"]
    assert hi < lo


def test_interpolated_pixels_reported():
    b = make_synthetic_bundle(size=200)
    q = assess_quality(b.elev, b.count, b.z_err, b.slope_err)
    assert q["interpolated_fraction"] > 0.8 and any("interpolated" in w for w in q["warnings"])


# ---------------- sunlight / Earth ----------------
def test_sun_overhead_no_shadow():
    r = analyze_illumination(mk_sky(100, 45, 180, 3), FLAT, UP, SIM)
    assert r["percent_illuminated"] == 100.0 and r["longest_darkness_hours"] == 0.0


def test_sun_behind_mountain_blocked():
    h = {"azimuth_deg": AZ, "elevation_deg": np.where((AZ < 20) | (AZ > 340), 2.86, -0.001)}
    blocked = analyze_illumination(mk_sky(0, 1.0, 180, 3), h, UP, SIM)
    assert blocked["percent_illuminated"] == 0.0 and blocked["terrain_blocked_hours"] > 23
    assert analyze_illumination(mk_sky(0, 5.0, 180, 3), h, UP, SIM)["percent_illuminated"] == 100.0


def test_slope_facing_away_not_lit():
    n = np.array([np.sin(np.radians(60)), 0, np.cos(np.radians(60))])   # tilted toward east
    r = analyze_illumination(mk_sky(270, 20, 180, 3), FLAT, n, SIM)    # sun in the west
    assert r["percent_illuminated"] == 0.0 and r["incidence_limited_hours"] > 23


def test_sunrise_time_refined_to_analytic_value():
    t = np.arange(0, 86401, 600.0)
    el = -1 + 2 * t / 86400
    sky = SkySeries(T0, t, {"sun": np.full(t.size, 90.0), "earth": np.full(t.size, 180.0)},
                    {"sun": el, "earth": np.full(t.size, 3.0)}, {"sun": np.full(t.size, 1.496e8), "earth": np.full(t.size, 384400.0)})
    H = {"azimuth_deg": AZ, "elevation_deg": np.full(AZ.size, 0.3)}
    r = analyze_illumination(sky, H, UP, SIM)
    rise = datetime.fromisoformat(r["transitions"][0]["time_utc"].replace("Z", "+00:00"))
    exp = (0.3 - np.degrees(np.arctan2(695700, 1.496e8)) + 1) / 2 * 86400    # upper limb at the horizon
    assert abs((rise - T0).total_seconds() - exp) < 2.0


def test_earth_below_horizon_not_visible_and_terrain_blocked():
    below = analyze_earth_visibility(mk_sky(0, 5, 180, -2), FLAT, SIM)
    assert below["visibility_percent"] == 0.0 and below["blackout_intervals"][0]["reason"] == "below_local_horizon"
    h = {"azimuth_deg": AZ, "elevation_deg": np.where((AZ < 20) | (AZ > 340), 2.86, -0.001)}
    peak = analyze_earth_visibility(mk_sky(0, 5, 0, 1.0), h, SIM)
    assert peak["terrain_obstruction_status"] == "PRESENT" and peak["blackout_intervals"][0]["reason"] == "terrain_blocked"
    assert analyze_earth_visibility(mk_sky(0, 5, 180, 3), FLAT, SIM)["visibility_percent"] == 100.0


def test_interval_builder_without_refinement():
    iv, tr = build_intervals([0, 10, 20, 30], [True, True, False, False])
    assert [i["state"] for i in iv] == [True, False] and len(tr) == 1


# ---------------- ephemeris contract (Member 1) ----------------
def _rows(n=5, step=600, bad=None):
    rows = []
    for i in range(n):
        d = {"datetime_utc": (T0 + timedelta(seconds=i * step)).isoformat(),
             "sun": {"azimuth_deg": 100.0 + i, "elevation_deg": 1.0, "range_km": 1.49e8},
             "earth": {"azimuth_deg": 200.0, "elevation_deg": 3.0, "range_km": 3.8e5}}
        rows.append(d)
    if bad:
        bad(rows)
    return rows


def test_member1_observation_dicts_accepted():
    s = from_observation_dicts(_rows())
    assert s.t_s.tolist() == [0, 600, 1200, 1800, 2400]


def test_contract_validation_rejects_bad_data():
    for mutate in (lambda r: r[2]["sun"].update(elevation_deg=None), lambda r: r[1]["earth"].update(elevation_deg=95.0),
                   lambda r: r.__setitem__(slice(None), r[:1])):
        try:
            from_observation_dicts(_rows(bad=mutate))
        except SkyDataError:
            continue
        raise AssertionError("bad contract data accepted")


def test_naive_timestamp_rejected():
    rows = _rows()
    rows[0]["datetime_utc"] = "2030-01-01T00:00:00"
    try:
        from_observation_dicts(rows)
    except SkyDataError:
        return
    raise AssertionError("naive timestamp accepted")


def test_adapter_uses_member1_client_and_caches(monkeypatch=None):
    import astronomy.api.horizons_client as hc
    from astronomy.models.landing_site import CelestialResult
    from app.terrain.ephemeris import astronomy_adapter as ad
    calls = []

    def fake(body_id, body_name, site, start, stop, step_size="1 h", quantities=""):
        calls.append((body_name, step_size, site.altitude_km))
        n = int((stop - start).total_seconds() // 600) + 1
        return [CelestialResult(body_name, body_id, site, start + timedelta(minutes=10 * i), azimuth_deg=90.0 + i,
                                elevation_deg=2.0, range_km=1.49e8 if body_name == "Sun" else 3.8e5) for i in range(n)]
    orig = hc.query_body_range
    hc.query_body_range = fake
    try:
        with tempfile.TemporaryDirectory() as d:
            s1 = ad.fetch_sky_series("t", -89.6, 30.0, 0.8, T0, T0 + timedelta(hours=2), 10, d)
            s2 = ad.fetch_sky_series("t", -89.6, 30.0, 0.8, T0, T0 + timedelta(hours=2), 10, d)
    finally:
        hc.query_body_range = orig
    assert s1.provenance["cache"] == "miss" and s2.provenance["cache"] == "hit" and len(calls) == 2
    assert calls[0][1] == "10 m" and s1.t_s.size == 13


# ---------------- scoring / ranking / uncertainty ----------------
def _fp(status, checks=None):
    return {"footprint_status": status, "checks": checks or [], "roughness_p95_m": 0.1}


def test_failed_hard_constraint_never_safe_even_with_perfect_scores():
    illum, comm = {"percent_illuminated": 100.0}, {"visibility_percent": 100.0}
    chk = [{"name": "max_slope_in_footprint", "status": "FAIL", "value": 20.0, "limit": 10.0}]
    a = assess(_fp("FAIL", chk), illum, comm, {"confidence_score": 100.0}, None, LanderSpec(), AnalysisConfig().scoring)
    assert a["status"] == "REJECTED_HARD_CONSTRAINT" and a["hard_constraint_failed"] and a["components"]["terrain_safety"] == 0.0


def test_ranking_puts_eligible_before_rejected_regardless_of_score():
    mk = lambda st, sc: {"assessment": {"status": st, "score": sc}}
    out = rank_sites([mk("REJECTED_HARD_CONSTRAINT", 99), mk("MEETS_CONFIGURED_CRITERIA", 40), mk("CONDITIONAL", 80)])
    assert [r["assessment"]["status"] for r in out] == ["MEETS_CONFIGURED_CRITERIA", "CONDITIONAL", "REJECTED_HARD_CONSTRAINT"]


def test_missing_components_reported_not_zeroed():
    a = assess(_fp("PASS"), None, None, {"confidence_score": 80.0}, None, LanderSpec(), AnalysisConfig().scoring)
    assert "sunlight" in a["missing_components"] and not a["score_complete"] and a["components"]["sunlight"] is None


def test_monte_carlo_deterministic_and_reports_indicator():
    f = lambda rng: rng.normal()
    ev = lambda p: {"status": "PASS" if p < 1.0 else "FAIL", "max_slope_deg": abs(p)}
    a, b = monte_carlo(200, 3, f, ev), monte_carlo(200, 3, f, ev)
    assert a == b and 70 < a["confidence_indicator_percent"] < 95 and "not a probability" in a["interpretation"]


def test_perturbation_scaled_by_error():
    rng = np.random.default_rng(0)
    p = perturbation_field((300, 300), np.full((300, 300), 2.0), 4, rng)
    assert 1.8 < p.std() < 2.2


def test_compare_arrays_known_bias():
    a = np.random.default_rng(1).normal(size=(50, 50)); r = compare_arrays(a + 0.5, a)
    assert abs(r["bias"] - 0.5) < 1e-9 and r["rmse"] > 0.49


def test_surface_normal_flat_is_up_and_tilt_matches():
    b = make_synthetic_bundle(size=100, craters=False, ridge=False, roughness_m=0.0)
    b.elev[:] = 0.0
    assert abs(surface_normal_enu(b.grid, b.elev, 50, 50, 2)[2] - 1.0) < 1e-6
    b.elev[:] = np.tan(np.radians(10)) * np.arange(100)[None, :] * 5.0
    assert abs(np.degrees(np.arccos(surface_normal_enu(b.grid, b.elev, 50, 50, 2)[2])) - 10.0) < 0.05


# ---------------- pipeline / config ----------------
def test_config_from_dict_ignores_unknown_and_parses_dates():
    c = config_from_dict({"bogus": 1, "lander": {"max_slope_deg": 7, "zzz": 1}, "sim": {"start_utc": "2030-01-01T00:00:00Z"}})
    assert c.lander.max_slope_deg == 7 and c.sim.start_utc.year == 2030


def test_clean_makes_json_safe():
    s = json.dumps(clean({"a": np.float64("nan"), "b": np.arange(3), "c": np.bool_(True), "d": T0}))
    assert "NaN" not in s


def test_pipeline_end_to_end_contract_and_honesty():
    b = make_synthetic_bundle(size=500, seed=7)
    cfg = AnalysisConfig(); cfg.uncertainty.runs = 5; cfg.window_radius_m = 1000
    r = run_analysis(b, cfg, sky=synthetic_sky(T0, 24 * 10, 20), point={"row": 250, "col": 250})
    json.dumps(r)
    for k in ("dataset", "terrain", "hazards", "illumination", "communication", "assessment", "provenance", "limitations", "maps", "horizon"):
        assert k in r
    assert r["dataset"]["real_data"] is False and "SYNTHETIC" in r["limitations"][0]
    assert r["hazards"]["footprint_status"] in ("PASS", "WARNING", "FAIL", "UNKNOWN")
    assert r["assessment"]["criteria_source"] == "DEMO_DEFAULTS"
    assert r["illumination"]["illumination_percent"] == r["illumination"]["percent_illuminated"]
    r2 = run_analysis(b, cfg, point={"row": 250, "col": 250})                 # no ephemeris -> nulls, not zeros
    assert r2["illumination"] is None and r2["communication"] is None and not r2["assessment"]["score_complete"]


def test_edge_point_rejected_clearly():
    b = make_synthetic_bundle(size=300)
    try:
        run_analysis(b, AnalysisConfig(), point={"row": 3, "col": 3})
    except ValueError as e:
        assert "tile edge" in str(e)
        return
    raise AssertionError("edge point accepted")
