"""
test_models.py — Unit tests for the data models
=================================================
Tests that do NOT require network access — purely local validation.
"""

import sys
sys.path.insert(0, r"c:\Users\Sachith A Rao\OneDrive\Desktop\NASA hackathon preparation")

import unittest
from datetime import datetime, timezone
from astronomy.models.landing_site import (
    LandingSite,
    CelestialResult,
    SiteObservation,
    SHACKLETON_RIM,
    ALL_CANDIDATE_SITES,
)


class TestLandingSite(unittest.TestCase):
    """Test LandingSite validation and formatting."""

    def test_valid_site_creation(self):
        site = LandingSite("Test", latitude=-89.0, longitude=45.0)
        self.assertEqual(site.name, "Test")
        self.assertEqual(site.latitude, -89.0)
        self.assertEqual(site.longitude, 45.0)
        self.assertEqual(site.altitude_km, 0.0)

    def test_site_coord_string(self):
        site = LandingSite("Test", latitude=-89.68, longitude=129.0, altitude_km=0.0)
        self.assertEqual(site.site_coord_string, "129.0,-89.68,0.0")

    def test_invalid_latitude_too_high(self):
        with self.assertRaises(ValueError):
            LandingSite("Bad", latitude=91.0, longitude=0.0)

    def test_invalid_latitude_too_low(self):
        with self.assertRaises(ValueError):
            LandingSite("Bad", latitude=-91.0, longitude=0.0)

    def test_invalid_longitude_too_low(self):
        with self.assertRaises(ValueError):
            LandingSite("Bad", latitude=0.0, longitude=-181.0)

    def test_invalid_longitude_too_high(self):
        with self.assertRaises(ValueError):
            LandingSite("Bad", latitude=0.0, longitude=361.0)

    def test_invalid_altitude_too_high(self):
        with self.assertRaises(ValueError):
            LandingSite("Bad", latitude=0.0, longitude=0.0, altitude_km=100.0)

    def test_frozen_immutability(self):
        with self.assertRaises(AttributeError):
            SHACKLETON_RIM.latitude = 0.0  # type: ignore

    def test_all_candidate_sites_valid(self):
        """Ensure all pre-defined sites pass validation."""
        self.assertEqual(len(ALL_CANDIDATE_SITES), 6)
        for site in ALL_CANDIDATE_SITES:
            self.assertIsInstance(site, LandingSite)
            self.assertTrue(-90 <= site.latitude <= 90)
            self.assertTrue(-180 <= site.longitude <= 360)


class TestCelestialResult(unittest.TestCase):
    """Test CelestialResult properties and serialisation."""

    def _make_result(self, elevation: float | None = 5.0) -> CelestialResult:
        return CelestialResult(
            target_body="Sun",
            target_id="10",
            site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            azimuth_deg=259.85,
            elevation_deg=elevation,
            ra_deg=341.99,
            dec_deg=-7.64,
            range_km=148_500_000.0,
            range_rate_km_s=0.85,
            illuminated_fraction=1.0,
            phase_angle_deg=0.0,
        )

    def test_above_horizon_positive(self):
        r = self._make_result(elevation=5.0)
        self.assertTrue(r.is_above_horizon)

    def test_below_horizon_negative(self):
        r = self._make_result(elevation=-0.5)
        self.assertFalse(r.is_above_horizon)

    def test_horizon_unknown(self):
        r = self._make_result(elevation=None)
        self.assertIsNone(r.is_above_horizon)

    def test_to_dict_keys(self):
        r = self._make_result()
        d = r.to_dict()
        expected_keys = {
            "target_body", "target_id", "site", "datetime_utc",
            "azimuth_deg", "elevation_deg", "ra_deg", "dec_deg",
            "range_km", "range_rate_km_s", "illuminated_fraction",
            "phase_angle_deg", "is_above_horizon",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_site_nested(self):
        r = self._make_result()
        d = r.to_dict()
        self.assertIn("name", d["site"])
        self.assertIn("latitude_deg", d["site"])


class TestSiteObservation(unittest.TestCase):
    """Test SiteObservation bundle."""

    def test_empty_observation(self):
        dt = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        obs = SiteObservation(site=SHACKLETON_RIM, datetime_utc=dt)
        self.assertIsNone(obs.sun)
        self.assertIsNone(obs.earth)

    def test_to_dict_with_none_bodies(self):
        dt = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        obs = SiteObservation(site=SHACKLETON_RIM, datetime_utc=dt)
        d = obs.to_dict()
        self.assertIsNone(d["sun"])
        self.assertIsNone(d["earth"])
        self.assertEqual(d["site"]["name"], "Peak Near Shackleton")


if __name__ == "__main__":
    unittest.main()

