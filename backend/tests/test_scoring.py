import math, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from scoring import haversine_km, route_stats, suitability, risk_class, R_MOON_KM

SITE = {"slope_deg": 5, "sunlight_pct": 75, "comms_pct": 95, "ice_score": 40, "hazard": 40, "science": 70}

def test_quarter_circumference():
    assert math.isclose(haversine_km(0, 0, 0, 90), math.pi / 2 * R_MOON_KM, rel_tol=1e-9)

def test_pole_to_pole():
    assert math.isclose(haversine_km(-90, 0, 90, 0), math.pi * R_MOON_KM, rel_tol=1e-9)

def test_zero_distance():
    assert haversine_km(10, 20, 10, 20) == 0

def test_score_range_and_weights():
    s = suitability(SITE)
    assert 0 <= s["score"] <= 100
    ice_only = suitability(SITE, {"slope": 0, "sun": 0, "comms": 0, "ice": 10, "hazard": 0, "science": 0})
    assert ice_only["score"] == 40

def test_risk():
    assert risk_class({**SITE, "hazard": 70}) == "High"
    assert risk_class({**SITE, "hazard": 50}) == "Moderate"
    assert risk_class(SITE) == "Low"

def test_route():
    pts = [{"lat": 0, "lon": 0, "name": "A"}, {"lat": 0, "lon": 1, "name": "B"}]
    r = route_stats(pts, speed_kmh=1, op_hours_per_day=8, margin_pct=0, stop_hours=0)
    assert math.isclose(r["total_km"], 30.32, abs_tol=0.01)
    assert math.isclose(r["duration_days"], 30.32 / 8, abs_tol=0.01)
