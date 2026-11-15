"""Pure scoring and routing logic (no third-party imports, easy to unit test).

All scores are a SIMULATED educational model, not an official NASA recommendation.
"""
import math

R_MOON_KM = 1737.4
DEFAULT_WEIGHTS = {"slope": 5, "sun": 5, "comms": 4, "ice": 4, "hazard": 5, "science": 3}
LABELS = {"slope": "Gentle slope", "sun": "Sunlight", "comms": "Earth visibility",
          "ice": "Water-ice potential", "hazard": "Low hazard", "science": "Science value"}
DISCLAIMER = "Simulated educational score; not an official NASA recommendation."


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * R_MOON_KM * math.asin(min(1.0, math.sqrt(a)))


def components(s):
    return {"slope": max(0.0, 100 - (s["slope_deg"] or 0) * 8), "sun": s["sunlight_pct"] or 0,
            "comms": s["comms_pct"] or 0, "ice": s["ice_score"] or 0,
            "hazard": 100 - (s["hazard"] or 0), "science": s["science"] or 0}


def risk_class(s):
    h, sl = s["hazard"] or 0, s["slope_deg"] or 0
    return "High" if h >= 65 or sl >= 10 else "Moderate" if h >= 45 else "Low"


def suitability(s, weights=None):
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    c = components(s)
    total = sum(w.values())
    value = round(sum(c[k] * w[k] for k in c) / total) if total else 0
    pros = [LABELS[k] for k in c if c[k] >= 70]
    cons = [LABELS[k] for k in c if c[k] <= 40]
    why = (f"Score {value}/100 is a weighted blend of slope, sunlight, comms, ice, hazard and science value. "
           f"Strengths: {', '.join(pros) or 'none strong'}. Weaknesses: {', '.join(cons) or 'none major'}.")
    return {"score": value, "risk": risk_class(s), "components": {k: round(v) for k, v in c.items()},
            "pros": pros, "cons": cons, "explanation": why, "disclaimer": DISCLAIMER}


def route_stats(points, speed_kmh, op_hours_per_day, margin_pct, stop_hours):
    """points[0] is the landing site; each later point is a waypoint."""
    legs, km = [], 0.0
    for a, b in zip(points, points[1:]):
        d = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
        legs.append({"from": a.get("name", ""), "to": b.get("name", ""), "km": round(d, 2)})
        km += d
    drive_h = km / speed_kmh * (1 + margin_pct / 100)
    total_h = drive_h + max(0, len(points) - 1) * stop_hours
    return {"legs": legs, "total_km": round(km, 2), "drive_hours": round(drive_h, 1),
            "total_hours": round(total_h, 1), "duration_days": round(total_h / op_hours_per_day, 2)}
