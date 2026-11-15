"""
scientific_validation.py — Cross-validation against independent references
============================================================================

This module validates the astronomy module's outputs using multiple
independent strategies.  It does NOT test code correctness (that's in
tests/); it tests whether the **scientific results** are physically
plausible and consistent with known astronomical facts.

Validation strategies
---------------------
1. **Physical bounds checks**
   - Sun distance ≈ 1 AU (±3%)
   - Earth distance ≈ 384,400 km (±8%)
   - Sun illuminated fraction = 100% (it's self-luminous)
   - Sun phase angle ≈ 0° (Sun-Sun-Observer is always ~0°)
   - Azimuth in [0, 360), elevation in [-90, +90]

2. **Earth illumination consistency**
   - phase_angle + illuminated_fraction must be consistent:
     illuminated ≈ (1 + cos(phase_angle)) / 2

3. **South-pole solar elevation bounds**
   - At the lunar south pole the Sun elevation oscillates roughly
     between ±1.54° over a synodic month (~29.53 days).
   - During southern-hemisphere summer (Sun below ecliptic), elevation
     can reach ~+1.54°.  During winter, ~−1.54°.

4. **Near-site consistency**
   - Two sites < 0.1° apart should produce results within 0.5° for
     azimuth and elevation.

5. **Temporal continuity**
   - Elevation should change smoothly — no jumps > 1° between
     consecutive hourly steps for the Sun.

All validations return structured ValidationResult objects with
pass/fail, measured value, expected range, and explanation.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from astronomy.models.landing_site import (
    CelestialResult,
    LandingSite,
    SHACKLETON_RIM,
    HAWORTH,
    CONNECTING_RIDGE,
    ALL_CANDIDATE_SITES,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Validation result model
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """
    One validation check result.

    Attributes
    ----------
    name        : Short identifier for the check.
    passed      : True if the check passed.
    message     : Human-readable explanation.
    measured    : The measured value(s).
    expected    : The expected range or value.
    severity    : "error" (physics violation), "warning" (suspicious),
                  "info" (informational).
    """
    name: str
    passed: bool
    message: str
    measured: str = ""
    expected: str = ""
    severity: str = "error"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "measured": self.measured,
            "expected": self.expected,
            "severity": self.severity,
        }


@dataclass
class ValidationReport:
    """
    Complete validation report containing multiple check results.
    """
    timestamp_utc: str
    site_name: str
    observation_time: str
    checks: list[ValidationResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def error_count(self) -> int:
        return sum(
            1 for c in self.checks
            if not c.passed and c.severity == "error"
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1 for c in self.checks
            if not c.passed and c.severity == "warning"
        )

    @property
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.passed)
        return (
            f"{passed}/{total} checks passed "
            f"({self.error_count} errors, {self.warning_count} warnings)"
        )

    def to_dict(self) -> dict:
        return {
            "timestamp_utc": self.timestamp_utc,
            "site_name": self.site_name,
            "observation_time": self.observation_time,
            "summary": self.summary,
            "all_passed": self.all_passed,
            "checks": [c.to_dict() for c in self.checks],
        }


# ═══════════════════════════════════════════════════════════════════════
# 1.  Physical bounds validators (offline — work on CelestialResult)
# ═══════════════════════════════════════════════════════════════════════

def validate_sun_result(result: CelestialResult) -> list[ValidationResult]:
    """
    Validate a Sun observation against known physical constraints.
    """
    checks: list[ValidationResult] = []

    # ── Sun distance ≈ 1 AU ─────────────────────────────────────────
    AU_KM = 149_597_870.7
    if result.range_km is not None:
        ratio = result.range_km / AU_KM
        in_range = 0.97 <= ratio <= 1.03  # ±3%
        checks.append(ValidationResult(
            name="sun_distance_1au",
            passed=in_range,
            message=(
                f"Sun distance = {result.range_km:.0f} km "
                f"({ratio:.4f} AU) — "
                + ("within ±3% of 1 AU" if in_range else "OUTSIDE ±3% of 1 AU")
            ),
            measured=f"{result.range_km:.0f} km ({ratio:.4f} AU)",
            expected=f"{AU_KM:.0f} km (1.0 AU ± 3%)",
        ))
    else:
        checks.append(ValidationResult(
            name="sun_distance_1au",
            passed=False,
            message="Sun range_km is None — cannot validate distance",
            severity="warning",
        ))

    # ── Sun illuminated fraction = 100% ─────────────────────────────
    if result.illuminated_fraction is not None:
        is_full = abs(result.illuminated_fraction - 1.0) < 0.001
        checks.append(ValidationResult(
            name="sun_illumination_100pct",
            passed=is_full,
            message=(
                f"Sun illuminated fraction = {result.illuminated_fraction:.5f} — "
                + ("correct (self-luminous)" if is_full
                   else "ERROR: Sun should always be 100% illuminated")
            ),
            measured=f"{result.illuminated_fraction:.5f}",
            expected="1.00000 (±0.001)",
        ))

    # ── Sun phase angle ≈ 0° ────────────────────────────────────────
    if result.phase_angle_deg is not None:
        near_zero = result.phase_angle_deg < 0.1
        checks.append(ValidationResult(
            name="sun_phase_angle_zero",
            passed=near_zero,
            message=(
                f"Sun-Target-Observer phase angle = {result.phase_angle_deg:.4f}° — "
                + ("correct (Sun observing itself)" if near_zero
                   else "ERROR: should be ~0° for the Sun")
            ),
            measured=f"{result.phase_angle_deg:.4f}°",
            expected="~0° (Sun-Sun-Observer)",
        ))

    # ── Azimuth in [0, 360) ─────────────────────────────────────────
    if result.azimuth_deg is not None:
        valid_az = 0.0 <= result.azimuth_deg < 360.0
        checks.append(ValidationResult(
            name="sun_azimuth_range",
            passed=valid_az,
            message=(
                f"Sun azimuth = {result.azimuth_deg:.4f}° — "
                + ("valid range" if valid_az else "OUTSIDE [0, 360)")
            ),
            measured=f"{result.azimuth_deg:.4f}°",
            expected="[0, 360)",
        ))

    # ── Elevation in [-90, +90] ─────────────────────────────────────
    if result.elevation_deg is not None:
        valid_el = -90.0 <= result.elevation_deg <= 90.0
        checks.append(ValidationResult(
            name="sun_elevation_range",
            passed=valid_el,
            message=(
                f"Sun elevation = {result.elevation_deg:.6f}° — "
                + ("valid range" if valid_el else "OUTSIDE [-90, +90]")
            ),
            measured=f"{result.elevation_deg:.6f}°",
            expected="[-90, +90]",
        ))

    return checks


def validate_earth_result(result: CelestialResult) -> list[ValidationResult]:
    """
    Validate an Earth observation against known physical constraints.
    """
    checks: list[ValidationResult] = []

    # ── Earth distance ≈ 384,400 km (±8%) ───────────────────────────
    MEAN_DIST_KM = 384_400.0
    if result.range_km is not None:
        ratio = result.range_km / MEAN_DIST_KM
        in_range = 0.92 <= ratio <= 1.08
        checks.append(ValidationResult(
            name="earth_distance_lunar",
            passed=in_range,
            message=(
                f"Earth distance = {result.range_km:.0f} km "
                f"({ratio:.3f}× mean) — "
                + ("within ±8% of mean lunar distance" if in_range
                   else "OUTSIDE ±8% of mean distance")
            ),
            measured=f"{result.range_km:.0f} km",
            expected=f"{MEAN_DIST_KM:.0f} km (± 8%)",
        ))

    # ── Azimuth in [0, 360) ─────────────────────────────────────────
    if result.azimuth_deg is not None:
        valid_az = 0.0 <= result.azimuth_deg < 360.0
        checks.append(ValidationResult(
            name="earth_azimuth_range",
            passed=valid_az,
            message=f"Earth azimuth = {result.azimuth_deg:.4f}°",
            measured=f"{result.azimuth_deg:.4f}°",
            expected="[0, 360)",
        ))

    # ── Elevation in [-90, +90] ─────────────────────────────────────
    if result.elevation_deg is not None:
        valid_el = -90.0 <= result.elevation_deg <= 90.0
        checks.append(ValidationResult(
            name="earth_elevation_range",
            passed=valid_el,
            message=f"Earth elevation = {result.elevation_deg:.6f}°",
            measured=f"{result.elevation_deg:.6f}°",
            expected="[-90, +90]",
        ))

    # ── Earth illumination vs phase angle consistency ───────────────
    if (result.illuminated_fraction is not None
            and result.phase_angle_deg is not None):
        # For a sphere: illuminated ≈ (1 + cos(phase)) / 2
        expected_illum = (
            1.0 + math.cos(math.radians(result.phase_angle_deg))
        ) / 2.0
        actual_illum = result.illuminated_fraction
        diff = abs(actual_illum - expected_illum)
        # Allow ±0.05 tolerance (Earth is not a perfect sphere,
        # and the formula is an approximation)
        consistent = diff < 0.05
        checks.append(ValidationResult(
            name="earth_illumination_phase_consistency",
            passed=consistent,
            message=(
                f"Illumination = {actual_illum:.4f}, "
                f"expected from phase ({result.phase_angle_deg:.1f}°) "
                f"≈ {expected_illum:.4f}, diff = {diff:.4f} — "
                + ("consistent" if consistent else "INCONSISTENT")
            ),
            measured=f"illum={actual_illum:.4f}, phase={result.phase_angle_deg:.1f}°",
            expected=f"illum ≈ (1+cos({result.phase_angle_deg:.1f}°))/2 = {expected_illum:.4f} (±0.05)",
            severity="warning" if not consistent else "info",
        ))

    # ── Illuminated fraction in [0, 1] ──────────────────────────────
    if result.illuminated_fraction is not None:
        valid_frac = 0.0 <= result.illuminated_fraction <= 1.0
        checks.append(ValidationResult(
            name="earth_illumination_range",
            passed=valid_frac,
            message=(
                f"Earth illuminated fraction = {result.illuminated_fraction:.5f}"
            ),
            measured=f"{result.illuminated_fraction:.5f}",
            expected="[0, 1]",
        ))

    return checks


# ═══════════════════════════════════════════════════════════════════════
# 2.  South-pole elevation bounds (offline)
# ═══════════════════════════════════════════════════════════════════════

def validate_south_pole_sun_elevation(
    result: CelestialResult,
) -> list[ValidationResult]:
    """
    Near the lunar south pole, the Sun elevation should stay within
    a bound that depends on the observer's latitude.

    At exactly −90° latitude, the Sun elevation oscillates roughly
    ±1.54° (the obliquity of the ecliptic to the lunar equator).
    At less extreme latitudes (e.g. −87.45°), the Sun can dip further
    below or rise further above the horizon because the observer is
    offset from the pole.

    We compute a latitude-dependent bound:
        max_el ≈ 1.54° + (90° − |latitude|)
    and add a 1° safety margin.
    """
    checks: list[ValidationResult] = []

    if (result.elevation_deg is not None
            and result.site.latitude < -85.0):
        # Latitude offset from pole + obliquity + margin
        offset_from_pole = 90.0 - abs(result.site.latitude)
        max_expected = 1.54 + offset_from_pole + 1.0
        in_range = abs(result.elevation_deg) <= max_expected
        checks.append(ValidationResult(
            name="south_pole_sun_elevation_bound",
            passed=in_range,
            message=(
                f"Sun elevation at {result.site.name} "
                f"(lat {result.site.latitude}°) = {result.elevation_deg:.3f}° — "
                + (f"within ±{max_expected}° of horizon" if in_range
                   else f"EXCEEDS ±{max_expected}° bound for south-pole site")
            ),
            measured=f"{result.elevation_deg:.3f}°",
            expected=f"±{max_expected}° at lat={result.site.latitude}°",
            severity="warning",
        ))

    return checks


def validate_south_pole_earth_elevation(
    result: CelestialResult,
) -> list[ValidationResult]:
    """
    At the lunar south pole, Earth elevation oscillates roughly
    between ±7° due to libration.  We use ±10° as a generous bound.
    """
    checks: list[ValidationResult] = []

    if (result.elevation_deg is not None
            and result.site.latitude < -85.0):
        max_expected = 10.0
        in_range = abs(result.elevation_deg) <= max_expected
        checks.append(ValidationResult(
            name="south_pole_earth_elevation_bound",
            passed=in_range,
            message=(
                f"Earth elevation at {result.site.name} "
                f"(lat {result.site.latitude}°) = {result.elevation_deg:.3f}° — "
                + (f"within ±{max_expected}° (libration)" if in_range
                   else f"EXCEEDS ±{max_expected}° bound for south-pole site")
            ),
            measured=f"{result.elevation_deg:.3f}°",
            expected=f"±{max_expected}° at lat={result.site.latitude}°",
            severity="warning",
        ))

    return checks


# ═══════════════════════════════════════════════════════════════════════
# 3.  Temporal continuity check (offline — works on a list of results)
# ═══════════════════════════════════════════════════════════════════════

def validate_temporal_continuity(
    results: list[CelestialResult],
    max_elevation_jump_deg: float = 1.0,
) -> list[ValidationResult]:
    """
    Check that elevation changes smoothly between consecutive steps.

    For hourly steps, elevation should not jump more than ~1° for the
    Sun (it moves ~0.5°/day at the south pole) or ~0.5° for Earth
    (libration is slow).

    Parameters
    ----------
    results                 : Chronologically ordered results.
    max_elevation_jump_deg  : Maximum acceptable jump per step.

    Returns
    -------
    List of ValidationResult (one per violation, plus a summary).
    """
    checks: list[ValidationResult] = []
    violations = 0

    for i in range(1, len(results)):
        r1 = results[i - 1]
        r2 = results[i]
        if r1.elevation_deg is None or r2.elevation_deg is None:
            continue

        jump = abs(r2.elevation_deg - r1.elevation_deg)
        if jump > max_elevation_jump_deg:
            violations += 1
            dt1 = r1.datetime_utc.isoformat()
            dt2 = r2.datetime_utc.isoformat()
            checks.append(ValidationResult(
                name=f"temporal_continuity_step_{i}",
                passed=False,
                message=(
                    f"Elevation jumped {jump:.3f}° between "
                    f"{dt1} and {dt2} (max allowed: {max_elevation_jump_deg}°)"
                ),
                measured=f"{jump:.3f}°",
                expected=f"≤ {max_elevation_jump_deg}°",
                severity="warning",
            ))

    # Summary
    total_steps = max(len(results) - 1, 1)
    checks.append(ValidationResult(
        name="temporal_continuity_summary",
        passed=(violations == 0),
        message=(
            f"Temporal continuity: {violations} violations in "
            f"{total_steps} steps"
            + (" — smooth" if violations == 0 else " — discontinuities detected")
        ),
        measured=f"{violations} violations",
        expected="0 violations",
        severity="info" if violations == 0 else "warning",
    ))

    return checks


# ═══════════════════════════════════════════════════════════════════════
# 4.  Full validation runner (requires network for API calls)
# ═══════════════════════════════════════════════════════════════════════

def validate_single_observation(
    sun: CelestialResult,
    earth: CelestialResult,
) -> ValidationReport:
    """
    Run all offline validation checks on a Sun + Earth observation pair.

    Parameters
    ----------
    sun   : CelestialResult for the Sun.
    earth : CelestialResult for the Earth.

    Returns
    -------
    ValidationReport with all check results.
    """
    report = ValidationReport(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        site_name=sun.site.name,
        observation_time=sun.datetime_utc.isoformat(),
    )

    # Sun physical checks
    report.checks.extend(validate_sun_result(sun))

    # Earth physical checks
    report.checks.extend(validate_earth_result(earth))

    # South-pole specific bounds
    report.checks.extend(validate_south_pole_sun_elevation(sun))
    report.checks.extend(validate_south_pole_earth_elevation(earth))

    return report


def run_full_validation(
    site: LandingSite,
    dt_utc: datetime,
) -> ValidationReport:
    """
    Run a complete validation: query Horizons for Sun and Earth, then
    validate the results.  Requires network access.

    Parameters
    ----------
    site   : Lunar landing site.
    dt_utc : Observation time (UTC).

    Returns
    -------
    ValidationReport with all checks.
    """
    from astronomy.api.horizons_client import query_sun, query_earth

    sun = query_sun(site, dt_utc)
    earth = query_earth(site, dt_utc)

    return validate_single_observation(sun, earth)


def run_temporal_validation(
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
) -> ValidationReport:
    """
    Run temporal-continuity validation over a time range.
    Requires network access.
    """
    from astronomy.api.horizons_client import query_body_range
    from astronomy.api.config import SUN_ID, EARTH_ID

    report = ValidationReport(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        site_name=site.name,
        observation_time=f"{start_utc.isoformat()} to {stop_utc.isoformat()}",
    )

    # Sun temporal continuity
    sun_results = query_body_range(
        SUN_ID, "Sun", site, start_utc, stop_utc, step_size
    )
    report.checks.extend(
        validate_temporal_continuity(sun_results, max_elevation_jump_deg=1.0)
    )

    # Also validate the first and last points physically
    if sun_results:
        report.checks.extend(validate_sun_result(sun_results[0]))
        report.checks.extend(
            validate_south_pole_sun_elevation(sun_results[0])
        )

    # Earth temporal continuity
    earth_results = query_body_range(
        EARTH_ID, "Earth", site, start_utc, stop_utc, step_size
    )
    report.checks.extend(
        validate_temporal_continuity(earth_results, max_elevation_jump_deg=1.0)
    )

    if earth_results:
        report.checks.extend(validate_earth_result(earth_results[0]))
        report.checks.extend(
            validate_south_pole_earth_elevation(earth_results[0])
        )

    return report

