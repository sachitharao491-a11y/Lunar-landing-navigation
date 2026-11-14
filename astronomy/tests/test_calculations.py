"""
test_calculations.py — Unit tests for geometry and calculation modules
========================================================================

All tests here are OFFLINE — they test pure-math functions that
require no network access.  Live integration tests that call the
Horizons API are gated behind HORIZONS_LIVE_TESTS=1.
"""

import sys
sys.path.insert(0, r"c:\Users\Sachith A Rao\OneDrive\Desktop\NASA hackathon preparation")

import math
import os
import unittest
from datetime import datetime, timezone

from astronomy.calculations.geometry import (
    angular_separation,
    clamp_elevation,
    compass_direction,
    elevation_rate_deg_per_hour,
    normalise_azimuth,
    shadow_length_ratio,
    solar_incidence_angle,
)

LIVE = os.environ.get("HORIZONS_LIVE_TESTS", "0") == "1"


# ═══════════════════════════════════════════════════════════════════════
# Geometry tests
# ═══════════════════════════════════════════════════════════════════════

class TestNormaliseAzimuth(unittest.TestCase):
    def test_zero(self):
        self.assertAlmostEqual(normalise_azimuth(0), 0.0)

    def test_positive_within_range(self):
        self.assertAlmostEqual(normalise_azimuth(180), 180.0)

    def test_full_circle(self):
        self.assertAlmostEqual(normalise_azimuth(360), 0.0)

    def test_negative(self):
        self.assertAlmostEqual(normalise_azimuth(-10), 350.0)

    def test_large_positive(self):
        self.assertAlmostEqual(normalise_azimuth(370), 10.0)

    def test_large_negative(self):
        self.assertAlmostEqual(normalise_azimuth(-370), 350.0)


class TestClampElevation(unittest.TestCase):
    def test_within_range(self):
        self.assertAlmostEqual(clamp_elevation(45.0), 45.0)

    def test_above_max(self):
        self.assertAlmostEqual(clamp_elevation(91.0), 90.0)

    def test_below_min(self):
        self.assertAlmostEqual(clamp_elevation(-91.0), -90.0)


class TestCompassDirection(unittest.TestCase):
    def test_north(self):
        self.assertEqual(compass_direction(0), "N")

    def test_east(self):
        self.assertEqual(compass_direction(90), "E")

    def test_south(self):
        self.assertEqual(compass_direction(180), "S")

    def test_west(self):
        self.assertEqual(compass_direction(270), "W")

    def test_northeast(self):
        self.assertEqual(compass_direction(45), "NE")

    def test_southwest(self):
        self.assertEqual(compass_direction(225), "SW")

    def test_wraparound(self):
        self.assertEqual(compass_direction(355), "N")

    def test_exact_boundary(self):
        # 11.25° is the boundary — falls into NNE due to rounding
        self.assertEqual(compass_direction(11.25), "NNE")
        # Just below the boundary → still N
        self.assertEqual(compass_direction(11.24), "N")

    def test_negative_azimuth(self):
        # -45° → 315° → NW
        self.assertEqual(compass_direction(-45), "NW")


class TestAngularSeparation(unittest.TestCase):
    def test_same_point(self):
        sep = angular_separation(100, 30, 100, 30)
        self.assertAlmostEqual(sep, 0.0, places=10)

    def test_opposite_hemisphere(self):
        # Zenith to nadir ≈ 180°
        sep = angular_separation(0, 90, 0, -90)
        self.assertAlmostEqual(sep, 180.0, places=5)

    def test_horizon_separation(self):
        # Due East vs Due West on the horizon
        sep = angular_separation(90, 0, 270, 0)
        self.assertAlmostEqual(sep, 180.0, places=5)

    def test_small_separation(self):
        sep = angular_separation(100, 30, 101, 30)
        # At el=30°, 1° of azimuth ≈ cos(30°) ≈ 0.866° of arc
        self.assertAlmostEqual(sep, 0.866, places=2)

    def test_north_south_symmetry(self):
        sep1 = angular_separation(0, 45, 180, 45)
        sep2 = angular_separation(180, 45, 0, 45)
        self.assertAlmostEqual(sep1, sep2, places=10)

    def test_known_90_degrees(self):
        # Zenith (0, 90) to horizon-East (90, 0) = 90°
        sep = angular_separation(0, 90, 90, 0)
        self.assertAlmostEqual(sep, 90.0, places=5)

    def test_real_sun_earth_from_horizons(self):
        """Use the actual Horizons data from our Phase 2 test."""
        # Sun:   az=259.853, el=-0.125
        # Earth: az=235.078, el=2.190
        sep = angular_separation(259.853, -0.125, 235.078, 2.190)
        # Should be roughly 25° (they're in the same quadrant of the sky)
        self.assertGreater(sep, 20)
        self.assertLess(sep, 30)


class TestShadowLengthRatio(unittest.TestCase):
    def test_45_degrees(self):
        # At 45°, shadow = object height
        ratio = shadow_length_ratio(45.0)
        self.assertAlmostEqual(ratio, 1.0, places=5)

    def test_90_degrees(self):
        # At zenith, shadow = 0
        ratio = shadow_length_ratio(90.0)
        self.assertAlmostEqual(ratio, 0.0, places=5)

    def test_low_sun(self):
        # At 1°, very long shadow
        ratio = shadow_length_ratio(1.0)
        self.assertGreater(ratio, 50)

    def test_below_horizon(self):
        self.assertIsNone(shadow_length_ratio(-5.0))

    def test_zero(self):
        self.assertIsNone(shadow_length_ratio(0.0))

    def test_30_degrees(self):
        # tan(30°) ≈ 0.577; ratio ≈ 1.732
        ratio = shadow_length_ratio(30.0)
        self.assertAlmostEqual(ratio, 1.0 / math.tan(math.radians(30)), places=4)


class TestSolarIncidenceAngle(unittest.TestCase):
    def test_flat_surface_overhead_sun(self):
        # Sun at zenith, flat surface → incidence = 0°
        angle = solar_incidence_angle(0, 90, 0, 0)
        self.assertAlmostEqual(angle, 0.0, places=3)

    def test_flat_surface_horizon_sun(self):
        # Sun at horizon (el=0), flat surface → incidence = 90°
        angle = solar_incidence_angle(90, 0, 0, 0)
        self.assertAlmostEqual(angle, 90.0, places=3)

    def test_flat_surface_45_sun(self):
        # Sun at 45° el, flat surface → incidence = 45°
        angle = solar_incidence_angle(0, 45, 0, 0)
        self.assertAlmostEqual(angle, 45.0, places=3)

    def test_vertical_wall_facing_sun(self):
        # Sun due North at el=0, wall facing North tilted 90° → incidence = 0°
        angle = solar_incidence_angle(0, 0, 90, 0)
        self.assertAlmostEqual(angle, 0.0, places=3)

    def test_vertical_wall_perpendicular_sun(self):
        # Sun due East at el=0, wall facing North tilted 90° → 90°
        angle = solar_incidence_angle(90, 0, 90, 0)
        self.assertAlmostEqual(angle, 90.0, places=3)


class TestElevationRate(unittest.TestCase):
    def test_rising(self):
        rate = elevation_rate_deg_per_hour(-1.0, 1.0, 2.0)
        self.assertAlmostEqual(rate, 1.0)  # 2° over 2 hours

    def test_setting(self):
        rate = elevation_rate_deg_per_hour(5.0, 3.0, 1.0)
        self.assertAlmostEqual(rate, -2.0)

    def test_zero_dt_raises(self):
        with self.assertRaises(ValueError):
            elevation_rate_deg_per_hour(0, 0, 0)

    def test_negative_dt_raises(self):
        with self.assertRaises(ValueError):
            elevation_rate_deg_per_hour(0, 1, -1)


# ═══════════════════════════════════════════════════════════════════════
# Earth visibility helper tests
# ═══════════════════════════════════════════════════════════════════════

from astronomy.calculations.earth_visibility import _phase_name


class TestPhaseName(unittest.TestCase):
    def test_new(self):
        self.assertEqual(_phase_name(0.005), "new")

    def test_crescent(self):
        self.assertEqual(_phase_name(0.15), "crescent")

    def test_quarter(self):
        self.assertEqual(_phase_name(0.30), "quarter")

    def test_gibbous(self):
        self.assertEqual(_phase_name(0.55), "gibbous")

    def test_nearly_full(self):
        self.assertEqual(_phase_name(0.85), "nearly full")

    def test_full(self):
        self.assertEqual(_phase_name(1.0), "full")

    def test_real_horizons_value(self):
        # From our Phase 2 test: illuminated_fraction = 0.0466
        self.assertEqual(_phase_name(0.0466), "crescent")


# ═══════════════════════════════════════════════════════════════════════
# Live integration tests (require network)
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipUnless(LIVE, "Set HORIZONS_LIVE_TESTS=1 to run live tests")
class TestLiveSolarAnalysis(unittest.TestCase):
    """Integration tests for solar.py — hit the real Horizons API."""

    def test_analyse_sun(self):
        from astronomy.calculations.solar import analyse_sun
        from astronomy.models.landing_site import SHACKLETON_RIM

        dt = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        result = analyse_sun(SHACKLETON_RIM, dt)

        self.assertIn("raw", result)
        self.assertIn("derived", result)
        self.assertIn("compass_direction", result["derived"])
        self.assertIn("is_sunlit", result["derived"])
        self.assertIn("shadow_length_ratio", result["derived"])
        self.assertIn("status", result["derived"])

    def test_compare_sites_sun(self):
        from astronomy.calculations.solar import compare_sites_sun
        from astronomy.models.landing_site import (
            SHACKLETON_RIM, HAWORTH, ALL_CANDIDATE_SITES,
        )

        dt = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        results = compare_sites_sun([SHACKLETON_RIM, HAWORTH], dt)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["site_name"], "Peak Near Shackleton")
        self.assertEqual(results[1]["site_name"], "Haworth")


@unittest.skipUnless(LIVE, "Set HORIZONS_LIVE_TESTS=1 to run live tests")
class TestLiveEarthAnalysis(unittest.TestCase):
    """Integration tests for earth_visibility.py."""

    def test_analyse_earth(self):
        from astronomy.calculations.earth_visibility import analyse_earth
        from astronomy.models.landing_site import SHACKLETON_RIM

        dt = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        result = analyse_earth(SHACKLETON_RIM, dt)

        self.assertIn("raw", result)
        self.assertIn("derived", result)
        self.assertIn("is_earth_visible", result["derived"])
        self.assertIn("communication_feasible", result["derived"])
        self.assertIn("earth_phase_name", result["derived"])


if __name__ == "__main__":
    unittest.main()
