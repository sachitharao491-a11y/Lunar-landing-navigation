"""
test_horizons_client.py — Tests for the Horizons API client
=============================================================

Contains:
    - Offline tests (no network) for input validation, URL building, parsing
    - Live integration tests (require network) marked with @unittest.skipUnless

Set the environment variable HORIZONS_LIVE_TESTS=1 to run live tests.
"""

import sys
sys.path.insert(0, r"c:\Users\Sachith A Rao\OneDrive\Desktop\NASA hackathon preparation")

import os
import unittest
from datetime import datetime, timedelta, timezone

from astronomy.api.config import (
    DEFAULT_QUANTITIES, EARTH_ID, HORIZONS_BASE_URL, SUN_ID,
)
from astronomy.api.exceptions import (
    HorizonsParseError,
    InvalidDateError,
)
from astronomy.api.horizons_client import (
    _build_params,
    _extract_ephemeris_block,
    _parse_data_row,
    _safe_float,
    _validate_datetime,
    query_body,
    query_earth,
    query_site,
    query_sun,
)
from astronomy.models.landing_site import (
    SHACKLETON_RIM,
    HAWORTH,
    LandingSite,
    CelestialResult,
)


# Whether to run tests that hit the real Horizons API
LIVE = os.environ.get("HORIZONS_LIVE_TESTS", "0") == "1"


# ═══════════════════════════════════════════════════════════════════════
# Offline unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestSafeFloat(unittest.TestCase):
    def test_normal(self):
        self.assertAlmostEqual(_safe_float("3.14"), 3.14)

    def test_negative(self):
        self.assertAlmostEqual(_safe_float("-0.125"), -0.125)

    def test_na(self):
        self.assertIsNone(_safe_float("n.a."))

    def test_na_upper(self):
        self.assertIsNone(_safe_float("N.A."))

    def test_empty(self):
        self.assertIsNone(_safe_float(""))

    def test_stars(self):
        self.assertIsNone(_safe_float("***"))

    def test_whitespace(self):
        self.assertAlmostEqual(_safe_float("  42.0  "), 42.0)


class TestBuildParams(unittest.TestCase):
    def test_basic_structure(self):
        dt = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        params = _build_params(
            SUN_ID, SHACKLETON_RIM,
            dt, dt + timedelta(minutes=1),
        )
        self.assertEqual(params["COMMAND"], "'10'")
        self.assertEqual(params["CENTER"], "'coord@301'")
        self.assertEqual(params["COORD_TYPE"], "'GEODETIC'")
        self.assertIn("129.0", params["SITE_COORD"])
        self.assertIn("-89.68", params["SITE_COORD"])

    def test_earth_command(self):
        dt = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        params = _build_params(
            EARTH_ID, SHACKLETON_RIM,
            dt, dt + timedelta(minutes=1),
        )
        self.assertEqual(params["COMMAND"], "'399'")


class TestValidateDatetime(unittest.TestCase):
    def test_valid_utc(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = _validate_datetime(dt)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_naive_assumed_utc(self):
        dt = datetime(2026, 1, 1)
        result = _validate_datetime(dt)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_too_early(self):
        with self.assertRaises(InvalidDateError):
            _validate_datetime(datetime(1500, 1, 1, tzinfo=timezone.utc))

    def test_too_late(self):
        with self.assertRaises(InvalidDateError):
            _validate_datetime(datetime(2600, 1, 1, tzinfo=timezone.utc))


class TestExtractEphemerisBlock(unittest.TestCase):
    def test_normal(self):
        text = "header\n$$SOE\ndata line 1\ndata line 2\n$$EOE\nfooter"
        block = _extract_ephemeris_block(text)
        self.assertIn("data line 1", block)
        self.assertIn("data line 2", block)

    def test_missing_soe(self):
        with self.assertRaises(HorizonsParseError):
            _extract_ephemeris_block("no markers here")


class TestParseDataRow(unittest.TestCase):
    """Test parsing of a real Horizons data row."""

    # Real row captured from the API
    REAL_ROW = " 2026-Mar-01 12:00 *i  341.988569022  -7.639342654  259.853369911  -0.124839033  100.00000  0.99311224907047   0.8523550    0.0000"

    def test_parse_sun_row(self):
        result = _parse_data_row(self.REAL_ROW, "10", "Sun", SHACKLETON_RIM)
        self.assertEqual(result.target_body, "Sun")
        self.assertEqual(result.target_id, "10")
        self.assertAlmostEqual(result.ra_deg, 341.988569022, places=5)
        self.assertAlmostEqual(result.dec_deg, -7.639342654, places=5)
        self.assertAlmostEqual(result.azimuth_deg, 259.853369911, places=5)
        self.assertAlmostEqual(result.elevation_deg, -0.124839033, places=5)
        self.assertAlmostEqual(result.illuminated_fraction, 1.0, places=3)
        self.assertIsNotNone(result.range_km)
        self.assertGreater(result.range_km, 100_000_000)  # ~1 AU in km
        self.assertAlmostEqual(result.phase_angle_deg, 0.0, places=2)
        self.assertFalse(result.is_above_horizon)  # elevation is negative

    EARTH_ROW = " 2026-Mar-01 12:00 *i  318.688266697 -17.856152848  235.077998890   2.190169583    4.66008  0.00251231661056   0.0324476  155.0612"

    def test_parse_earth_row(self):
        result = _parse_data_row(self.EARTH_ROW, "399", "Earth", SHACKLETON_RIM)
        self.assertEqual(result.target_body, "Earth")
        self.assertAlmostEqual(result.azimuth_deg, 235.078, places=2)
        self.assertAlmostEqual(result.elevation_deg, 2.190, places=2)
        self.assertTrue(result.is_above_horizon)
        # Earth range should be ~380,000 km
        self.assertIsNotNone(result.range_km)
        self.assertGreater(result.range_km, 350_000)
        self.assertLess(result.range_km, 420_000)


# ═══════════════════════════════════════════════════════════════════════
# Live integration tests (require network)
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipUnless(LIVE, "Set HORIZONS_LIVE_TESTS=1 to run live tests")
class TestLiveQueries(unittest.TestCase):
    """Integration tests that hit the real JPL Horizons API."""

    DT = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

    def test_query_sun(self):
        result = query_sun(SHACKLETON_RIM, self.DT)
        self.assertEqual(result.target_body, "Sun")
        self.assertIsNotNone(result.azimuth_deg)
        self.assertIsNotNone(result.elevation_deg)
        self.assertIsNotNone(result.range_km)

    def test_query_earth(self):
        result = query_earth(SHACKLETON_RIM, self.DT)
        self.assertEqual(result.target_body, "Earth")
        self.assertIsNotNone(result.azimuth_deg)
        self.assertIsNotNone(result.elevation_deg)

    def test_query_site(self):
        obs = query_site(HAWORTH, self.DT)
        self.assertIsNotNone(obs.sun)
        self.assertIsNotNone(obs.earth)
        self.assertEqual(obs.site.name, "Haworth")

    def test_different_sites_give_different_results(self):
        r1 = query_sun(SHACKLETON_RIM, self.DT)
        r2 = query_sun(HAWORTH, self.DT)
        # Same target, different observer → azimuth should differ
        self.assertNotAlmostEqual(r1.azimuth_deg, r2.azimuth_deg, places=1)

    def test_result_json_serialisable(self):
        import json
        result = query_sun(SHACKLETON_RIM, self.DT)
        text = json.dumps(result.to_dict())
        self.assertIn("Sun", text)


if __name__ == "__main__":
    unittest.main()

