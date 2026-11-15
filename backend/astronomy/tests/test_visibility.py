"""
test_visibility.py — Tests for geometric visibility determination
===================================================================

Offline tests cover:
    - Angular radius computation
    - Visible fraction of disk
    - Visibility state classification
    - Horizon crossing interpolation logic

Live tests (HORIZONS_LIVE_TESTS=1) cover:
    - Real visibility queries against JPL Horizons
"""

import sys
sys.path.insert(0, r"c:\Users\Sachith A Rao\OneDrive\Desktop\NASA hackathon preparation")

import math
import os
import unittest
from datetime import datetime, timedelta, timezone

from astronomy.calculations.visibility import (
    VisibilityState,
    VisibilityResult,
    HorizonEvent,
    compute_angular_radius,
    compute_visible_fraction,
    classify_visibility,
    assess_visibility,
    SUN_RADIUS_KM,
    EARTH_RADIUS_KM,
    SUN_DEFAULT_ANGULAR_RADIUS_DEG,
    EARTH_DEFAULT_ANGULAR_RADIUS_DEG,
)
from astronomy.models.landing_site import (
    CelestialResult,
    LandingSite,
    SHACKLETON_RIM,
    HAWORTH,
)

LIVE = os.environ.get("HORIZONS_LIVE_TESTS", "0") == "1"


# ═══════════════════════════════════════════════════════════════════════
# Angular radius tests
# ═══════════════════════════════════════════════════════════════════════

class TestComputeAngularRadius(unittest.TestCase):

    def test_sun_at_1_au(self):
        """Sun angular radius at 1 AU ≈ 0.267°."""
        au_km = 149_597_870.7
        ar = compute_angular_radius(SUN_RADIUS_KM, au_km, 0.0)
        self.assertAlmostEqual(ar, 0.267, places=2)

    def test_earth_at_mean_distance(self):
        """Earth angular radius at 384,400 km ≈ 0.95°."""
        ar = compute_angular_radius(EARTH_RADIUS_KM, 384_400, 0.0)
        self.assertAlmostEqual(ar, 0.95, places=1)

    def test_earth_at_perigee(self):
        """Earth angular radius at closest approach ≈ 1.02°."""
        ar = compute_angular_radius(EARTH_RADIUS_KM, 356_500, 0.0)
        self.assertGreater(ar, 1.0)

    def test_earth_at_apogee(self):
        """Earth angular radius at farthest distance ≈ 0.90°."""
        ar = compute_angular_radius(EARTH_RADIUS_KM, 406_700, 0.0)
        self.assertLess(ar, 0.95)

    def test_none_range_returns_default(self):
        ar = compute_angular_radius(SUN_RADIUS_KM, None, 0.267)
        self.assertAlmostEqual(ar, 0.267)

    def test_zero_range_returns_default(self):
        ar = compute_angular_radius(SUN_RADIUS_KM, 0, 0.267)
        self.assertAlmostEqual(ar, 0.267)


# ═══════════════════════════════════════════════════════════════════════
# Visible fraction tests
# ═══════════════════════════════════════════════════════════════════════

class TestComputeVisibleFraction(unittest.TestCase):

    def test_fully_above(self):
        """Center well above horizon → 100%."""
        frac = compute_visible_fraction(10.0, 0.267)
        self.assertAlmostEqual(frac, 1.0)

    def test_fully_below(self):
        """Center well below horizon → 0%."""
        frac = compute_visible_fraction(-10.0, 0.267)
        self.assertAlmostEqual(frac, 0.0)

    def test_center_on_horizon(self):
        """Center exactly on horizon → 50%."""
        frac = compute_visible_fraction(0.0, 0.267)
        self.assertAlmostEqual(frac, 0.5, places=3)

    def test_upper_limb_on_horizon(self):
        """Center at -radius → upper limb just touching horizon → 0%."""
        frac = compute_visible_fraction(-0.267, 0.267)
        self.assertAlmostEqual(frac, 0.0, places=3)

    def test_lower_limb_on_horizon(self):
        """Center at +radius → lower limb just touching horizon → 100%."""
        frac = compute_visible_fraction(0.267, 0.267)
        self.assertAlmostEqual(frac, 1.0, places=3)

    def test_half_below(self):
        """Center at -0.5*radius → about 20% visible."""
        frac = compute_visible_fraction(-0.1335, 0.267)
        self.assertGreater(frac, 0.1)
        self.assertLess(frac, 0.4)

    def test_monotonically_increasing(self):
        """Visible fraction should increase as elevation increases."""
        radius = 0.95  # Earth
        elevations = [-1.5, -0.95, -0.5, 0.0, 0.5, 0.95, 1.5]
        fractions = [compute_visible_fraction(e, radius) for e in elevations]
        for i in range(len(fractions) - 1):
            self.assertLessEqual(fractions[i], fractions[i + 1])

    def test_symmetry(self):
        """Fraction at +h and -h should sum to 1.0."""
        radius = 0.267
        for h_frac in [0.1, 0.3, 0.5, 0.7, 0.9]:
            h = h_frac * radius
            f_pos = compute_visible_fraction(h, radius)
            f_neg = compute_visible_fraction(-h, radius)
            self.assertAlmostEqual(f_pos + f_neg, 1.0, places=5)


# ═══════════════════════════════════════════════════════════════════════
# Visibility classification tests
# ═══════════════════════════════════════════════════════════════════════

class TestClassifyVisibility(unittest.TestCase):

    def test_fully_visible(self):
        # elevation > angular_radius
        state = classify_visibility(5.0, 0.267)
        self.assertEqual(state, VisibilityState.FULLY_VISIBLE)

    def test_partially_visible_positive_el(self):
        # 0 < elevation < angular_radius → upper part visible
        state = classify_visibility(0.1, 0.267)
        self.assertEqual(state, VisibilityState.PARTIALLY_VISIBLE)

    def test_partially_visible_negative_el(self):
        # -angular_radius < elevation < 0 → upper limb still above
        state = classify_visibility(-0.1, 0.267)
        self.assertEqual(state, VisibilityState.PARTIALLY_VISIBLE)

    def test_not_visible(self):
        # elevation < -angular_radius
        state = classify_visibility(-5.0, 0.267)
        self.assertEqual(state, VisibilityState.NOT_VISIBLE)

    def test_exactly_at_negative_radius(self):
        # Upper limb exactly at horizon → transition to NOT_VISIBLE
        state = classify_visibility(-0.267, 0.267)
        self.assertEqual(state, VisibilityState.NOT_VISIBLE)

    def test_exactly_at_positive_radius(self):
        # Lower limb exactly at horizon → FULLY_VISIBLE
        state = classify_visibility(0.267, 0.267)
        self.assertEqual(state, VisibilityState.FULLY_VISIBLE)

    def test_unknown_elevation(self):
        state = classify_visibility(None, 0.267)
        self.assertEqual(state, VisibilityState.UNKNOWN)

    def test_earth_large_radius(self):
        """Earth's larger angular radius → wider partial zone."""
        # Earth at 0.5° elevation with 0.95° radius → partially visible
        state = classify_visibility(0.5, 0.95)
        self.assertEqual(state, VisibilityState.PARTIALLY_VISIBLE)

        # Earth at 1.0° with 0.95° radius → fully visible
        state = classify_visibility(1.0, 0.95)
        self.assertEqual(state, VisibilityState.FULLY_VISIBLE)


# ═══════════════════════════════════════════════════════════════════════
# Assess visibility from CelestialResult
# ═══════════════════════════════════════════════════════════════════════

class TestAssessVisibility(unittest.TestCase):

    def _make_result(self, el: float, range_km: float = 149_597_870.7) -> CelestialResult:
        return CelestialResult(
            target_body="Sun",
            target_id="10",
            site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            azimuth_deg=259.85,
            elevation_deg=el,
            range_km=range_km,
        )

    def test_sun_just_below_horizon(self):
        """From Phase 2: Sun at -0.125° — should be PARTIALLY_VISIBLE."""
        r = self._make_result(-0.125)
        vis = assess_visibility(r, SUN_RADIUS_KM, SUN_DEFAULT_ANGULAR_RADIUS_DEG)
        self.assertEqual(vis.state, VisibilityState.PARTIALLY_VISIBLE)
        # Upper limb ≈ -0.125 + 0.267 ≈ +0.142° → above horizon
        self.assertGreater(vis.upper_limb_elevation_deg, 0)
        # Visible fraction should be > 0 but < 1
        self.assertGreater(vis.visible_fraction, 0.0)
        self.assertLess(vis.visible_fraction, 1.0)

    def test_sun_well_above(self):
        r = self._make_result(5.0)
        vis = assess_visibility(r, SUN_RADIUS_KM, SUN_DEFAULT_ANGULAR_RADIUS_DEG)
        self.assertEqual(vis.state, VisibilityState.FULLY_VISIBLE)
        self.assertAlmostEqual(vis.visible_fraction, 1.0)

    def test_sun_well_below(self):
        r = self._make_result(-5.0)
        vis = assess_visibility(r, SUN_RADIUS_KM, SUN_DEFAULT_ANGULAR_RADIUS_DEG)
        self.assertEqual(vis.state, VisibilityState.NOT_VISIBLE)
        self.assertAlmostEqual(vis.visible_fraction, 0.0)

    def test_earth_visible(self):
        """From Phase 2: Earth at +2.19° with range 375837 km."""
        r = CelestialResult(
            target_body="Earth",
            target_id="399",
            site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            azimuth_deg=235.08,
            elevation_deg=2.19,
            range_km=375_837.0,
        )
        vis = assess_visibility(r, EARTH_RADIUS_KM, EARTH_DEFAULT_ANGULAR_RADIUS_DEG)
        self.assertEqual(vis.state, VisibilityState.FULLY_VISIBLE)
        # Angular radius at 375837 km ≈ 0.97°
        self.assertAlmostEqual(vis.angular_radius_deg, 0.97, places=1)
        # Lower limb ≈ 2.19 - 0.97 ≈ +1.22° → above horizon → fully visible
        self.assertGreater(vis.lower_limb_elevation_deg, 0)

    def test_to_dict_has_warning(self):
        r = self._make_result(5.0)
        vis = assess_visibility(r, SUN_RADIUS_KM, SUN_DEFAULT_ANGULAR_RADIUS_DEG)
        d = vis.to_dict()
        self.assertIn("note", d)
        self.assertIn("geometric", d["note"].lower())
        self.assertTrue(d["is_geometric_only"])


# ═══════════════════════════════════════════════════════════════════════
# VisibilityResult serialisation
# ═══════════════════════════════════════════════════════════════════════

class TestVisibilityResultDict(unittest.TestCase):

    def test_all_keys_present(self):
        r = CelestialResult(
            target_body="Sun", target_id="10", site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 3, 1, tzinfo=timezone.utc),
            azimuth_deg=100, elevation_deg=5, range_km=149_000_000,
        )
        vis = assess_visibility(r, SUN_RADIUS_KM, SUN_DEFAULT_ANGULAR_RADIUS_DEG)
        d = vis.to_dict()
        expected_keys = {
            "body_name", "datetime_utc", "site", "state",
            "elevation_deg", "azimuth_deg", "angular_radius_deg",
            "upper_limb_elevation_deg", "lower_limb_elevation_deg",
            "visible_fraction", "range_km", "is_geometric_only", "note",
        }
        self.assertEqual(set(d.keys()), expected_keys)


# ═══════════════════════════════════════════════════════════════════════
# Live integration tests
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipUnless(LIVE, "Set HORIZONS_LIVE_TESTS=1 to run live tests")
class TestLiveVisibility(unittest.TestCase):

    DT = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

    def test_sun_visibility_single(self):
        from astronomy.calculations.visibility import sun_visibility
        vis = sun_visibility(SHACKLETON_RIM, self.DT)
        self.assertIn(vis.state, list(VisibilityState))
        self.assertIsNotNone(vis.elevation_deg)
        self.assertIsNotNone(vis.visible_fraction)

    def test_earth_visibility_single(self):
        from astronomy.calculations.visibility import earth_visibility
        vis = earth_visibility(SHACKLETON_RIM, self.DT)
        self.assertIn(vis.state, list(VisibilityState))

    def test_full_visibility_report(self):
        from astronomy.calculations.visibility import full_visibility_report
        report = full_visibility_report(SHACKLETON_RIM, self.DT)
        self.assertIn("sun", report)
        self.assertIn("earth", report)
        self.assertIn("summary", report)
        self.assertIn("lighting_condition", report["summary"])

    def test_compare_sites(self):
        from astronomy.calculations.visibility import compare_sites_visibility
        reports = compare_sites_visibility(
            [SHACKLETON_RIM, HAWORTH], self.DT
        )
        self.assertEqual(len(reports), 2)


if __name__ == "__main__":
    unittest.main()

