"""
test_validation.py — Tests for the scientific validation module
=================================================================

Offline tests use the real Horizons data captured in Phase 2 to
verify that all validators produce correct pass/fail judgements.

Live tests (HORIZONS_LIVE_TESTS=1) run the full validation pipeline
against real API data.
"""

import sys
sys.path.insert(0, r"c:\Users\Sachith A Rao\OneDrive\Desktop\NASA hackathon preparation")

import os
import unittest
from datetime import datetime, timezone

from astronomy.models.landing_site import (
    CelestialResult,
    LandingSite,
    SHACKLETON_RIM,
    HAWORTH,
)
from astronomy.validation.scientific_validation import (
    ValidationResult,
    ValidationReport,
    validate_sun_result,
    validate_earth_result,
    validate_south_pole_sun_elevation,
    validate_south_pole_earth_elevation,
    validate_temporal_continuity,
    validate_single_observation,
)

LIVE = os.environ.get("HORIZONS_LIVE_TESTS", "0") == "1"

# ── Real data from Phase 2 live test ────────────────────────────────
# Shackleton Rim, 2026-Mar-01 12:00 UTC
REAL_SUN = CelestialResult(
    target_body="Sun", target_id="10", site=SHACKLETON_RIM,
    datetime_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    azimuth_deg=259.853369911,
    elevation_deg=-0.124839033,
    ra_deg=341.988569022,
    dec_deg=-7.639342654,
    range_km=148_567_478.0,
    range_rate_km_s=0.852355,
    illuminated_fraction=1.0,
    phase_angle_deg=0.0,
)

REAL_EARTH = CelestialResult(
    target_body="Earth", target_id="399", site=SHACKLETON_RIM,
    datetime_utc=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    azimuth_deg=235.07799889,
    elevation_deg=2.190169583,
    ra_deg=318.688266697,
    dec_deg=-17.856152848,
    range_km=375_837.0,
    range_rate_km_s=0.0324476,
    illuminated_fraction=0.0466008,
    phase_angle_deg=155.0612,
)


# ═══════════════════════════════════════════════════════════════════════
# Sun validation tests
# ═══════════════════════════════════════════════════════════════════════

class TestValidateSunResult(unittest.TestCase):
    """Validate real Sun data from Phase 2."""

    def test_all_checks_pass(self):
        checks = validate_sun_result(REAL_SUN)
        for c in checks:
            self.assertTrue(c.passed, f"Check '{c.name}' failed: {c.message}")

    def test_sun_distance_check(self):
        checks = validate_sun_result(REAL_SUN)
        dist_check = next(c for c in checks if c.name == "sun_distance_1au")
        self.assertTrue(dist_check.passed)
        self.assertIn("AU", dist_check.measured)

    def test_sun_illumination_100(self):
        checks = validate_sun_result(REAL_SUN)
        illum_check = next(c for c in checks if c.name == "sun_illumination_100pct")
        self.assertTrue(illum_check.passed)

    def test_sun_phase_angle_zero(self):
        checks = validate_sun_result(REAL_SUN)
        phase_check = next(c for c in checks if c.name == "sun_phase_angle_zero")
        self.assertTrue(phase_check.passed)

    def test_bad_sun_distance_fails(self):
        """Fabricated Sun at wrong distance should fail."""
        bad_sun = CelestialResult(
            target_body="Sun", target_id="10", site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            range_km=50_000_000.0,  # Way too close
            illuminated_fraction=1.0,
            phase_angle_deg=0.0,
            azimuth_deg=180.0,
            elevation_deg=1.0,
        )
        checks = validate_sun_result(bad_sun)
        dist_check = next(c for c in checks if c.name == "sun_distance_1au")
        self.assertFalse(dist_check.passed)

    def test_bad_illumination_fails(self):
        """Sun with non-100% illumination should fail."""
        bad_sun = CelestialResult(
            target_body="Sun", target_id="10", site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            range_km=149_597_870.0,
            illuminated_fraction=0.5,  # Impossible for the Sun
            phase_angle_deg=0.0,
            azimuth_deg=180.0,
            elevation_deg=1.0,
        )
        checks = validate_sun_result(bad_sun)
        illum_check = next(c for c in checks if c.name == "sun_illumination_100pct")
        self.assertFalse(illum_check.passed)


# ═══════════════════════════════════════════════════════════════════════
# Earth validation tests
# ═══════════════════════════════════════════════════════════════════════

class TestValidateEarthResult(unittest.TestCase):
    """Validate real Earth data from Phase 2."""

    def test_all_checks_pass(self):
        checks = validate_earth_result(REAL_EARTH)
        for c in checks:
            self.assertTrue(c.passed, f"Check '{c.name}' failed: {c.message}")

    def test_earth_distance(self):
        checks = validate_earth_result(REAL_EARTH)
        dist = next(c for c in checks if c.name == "earth_distance_lunar")
        self.assertTrue(dist.passed)

    def test_earth_illumination_phase_consistency(self):
        """Phase 2 data: illum=0.0466, phase=155.06°.
        Expected: (1+cos(155.06°))/2 ≈ 0.0467 — should be consistent.
        """
        checks = validate_earth_result(REAL_EARTH)
        consist = next(
            c for c in checks if c.name == "earth_illumination_phase_consistency"
        )
        self.assertTrue(consist.passed)

    def test_bad_earth_distance_fails(self):
        bad_earth = CelestialResult(
            target_body="Earth", target_id="399", site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            range_km=100_000.0,  # Way too close
            azimuth_deg=200.0,
            elevation_deg=3.0,
            illuminated_fraction=0.5,
            phase_angle_deg=90.0,
        )
        checks = validate_earth_result(bad_earth)
        dist = next(c for c in checks if c.name == "earth_distance_lunar")
        self.assertFalse(dist.passed)


# ═══════════════════════════════════════════════════════════════════════
# South-pole elevation bounds tests
# ═══════════════════════════════════════════════════════════════════════

class TestSouthPoleElevationBounds(unittest.TestCase):

    def test_sun_elevation_at_south_pole_passes(self):
        """Real data: Sun at -0.125° from lat -89.68° — well within ±3°."""
        checks = validate_south_pole_sun_elevation(REAL_SUN)
        self.assertTrue(len(checks) > 0)
        self.assertTrue(checks[0].passed)

    def test_earth_elevation_at_south_pole_passes(self):
        """Real data: Earth at +2.19° from lat -89.68° — within ±10°."""
        checks = validate_south_pole_earth_elevation(REAL_EARTH)
        self.assertTrue(len(checks) > 0)
        self.assertTrue(checks[0].passed)

    def test_sun_extreme_elevation_fails(self):
        """Fabricated Sun at 20° from south pole — impossible."""
        bad = CelestialResult(
            target_body="Sun", target_id="10",
            site=SHACKLETON_RIM,
            datetime_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            elevation_deg=20.0,
            azimuth_deg=0.0,
        )
        checks = validate_south_pole_sun_elevation(bad)
        self.assertFalse(checks[0].passed)

    def test_non_polar_site_skipped(self):
        """Sites not near the pole should produce no checks."""
        equatorial = CelestialResult(
            target_body="Sun", target_id="10",
            site=LandingSite("Equator", latitude=0.0, longitude=0.0),
            datetime_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            elevation_deg=45.0,
            azimuth_deg=180.0,
        )
        checks = validate_south_pole_sun_elevation(equatorial)
        self.assertEqual(len(checks), 0)


# ═══════════════════════════════════════════════════════════════════════
# Temporal continuity tests
# ═══════════════════════════════════════════════════════════════════════

class TestTemporalContinuity(unittest.TestCase):

    def _make_results(self, elevations: list[float]) -> list[CelestialResult]:
        base = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        return [
            CelestialResult(
                target_body="Sun", target_id="10", site=SHACKLETON_RIM,
                datetime_utc=base + __import__("datetime").timedelta(hours=i),
                elevation_deg=el, azimuth_deg=180.0,
            )
            for i, el in enumerate(elevations)
        ]

    def test_smooth_passes(self):
        results = self._make_results([0.0, 0.1, 0.2, 0.3, 0.4])
        checks = validate_temporal_continuity(results, max_elevation_jump_deg=1.0)
        summary = next(c for c in checks if c.name == "temporal_continuity_summary")
        self.assertTrue(summary.passed)

    def test_jump_detected(self):
        results = self._make_results([0.0, 0.1, 5.0, 0.3, 0.4])  # 4.9° jump
        checks = validate_temporal_continuity(results, max_elevation_jump_deg=1.0)
        summary = next(c for c in checks if c.name == "temporal_continuity_summary")
        self.assertFalse(summary.passed)

    def test_single_result_no_crash(self):
        results = self._make_results([1.0])
        checks = validate_temporal_continuity(results)
        self.assertTrue(len(checks) > 0)


# ═══════════════════════════════════════════════════════════════════════
# Full observation validation
# ═══════════════════════════════════════════════════════════════════════

class TestValidateSingleObservation(unittest.TestCase):

    def test_real_data_all_pass(self):
        """All checks should pass on real Phase 2 Horizons data."""
        report = validate_single_observation(REAL_SUN, REAL_EARTH)
        self.assertTrue(
            report.all_passed,
            f"Validation failed: {report.summary}\n"
            + "\n".join(
                f"  ✗ {c.name}: {c.message}"
                for c in report.checks if not c.passed
            )
        )

    def test_report_has_all_fields(self):
        report = validate_single_observation(REAL_SUN, REAL_EARTH)
        d = report.to_dict()
        self.assertIn("summary", d)
        self.assertIn("all_passed", d)
        self.assertIn("checks", d)
        self.assertGreater(len(d["checks"]), 8)

    def test_report_summary_string(self):
        report = validate_single_observation(REAL_SUN, REAL_EARTH)
        self.assertIn("passed", report.summary)


# ═══════════════════════════════════════════════════════════════════════
# Live validation (requires network)
# ═══════════════════════════════════════════════════════════════════════

@unittest.skipUnless(LIVE, "Set HORIZONS_LIVE_TESTS=1 to run live tests")
class TestLiveValidation(unittest.TestCase):

    def test_full_validation_shackleton(self):
        from astronomy.validation.scientific_validation import run_full_validation
        dt = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        report = run_full_validation(SHACKLETON_RIM, dt)
        self.assertTrue(
            report.all_passed,
            f"Live validation failed: {report.summary}"
        )

    def test_full_validation_haworth(self):
        from astronomy.validation.scientific_validation import run_full_validation
        dt = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
        report = run_full_validation(HAWORTH, dt)
        self.assertTrue(
            report.all_passed,
            f"Live validation failed: {report.summary}"
        )


if __name__ == "__main__":
    unittest.main()

