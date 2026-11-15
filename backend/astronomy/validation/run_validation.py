"""
Phase 5 — Live validation runner.

Queries JPL Horizons for real data and runs all scientific validation
checks.  Prints a complete validation report.
"""

import sys
from pathlib import Path

# Support both `python -m astronomy.validation.run_validation` from the
# repository root and direct execution from another working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import json
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from astronomy.validation.scientific_validation import (
    run_full_validation,
    run_temporal_validation,
)
from astronomy.models.landing_site import (
    SHACKLETON_RIM,
    HAWORTH,
    DE_GERLACHE_RIM_1,
)
from astronomy.api.exceptions import HorizonsConnectionError, HorizonsAPIError


def run_all():
    print("=" * 72)
    print("PHASE 5 — SCIENTIFIC VALIDATION AGAINST JPL HORIZONS")
    print("=" * 72)

    # ── Test 1: Single-instant validation at Shackleton ─────────────
    print("\n── Test 1: Shackleton Rim, 2026-Mar-01 12:00 UTC ──")
    dt1 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    report1 = run_full_validation(SHACKLETON_RIM, dt1)
    _print_report(report1)

    # ── Test 2: Different site and date ─────────────────────────────
    print("\n── Test 2: Haworth, 2026-Jun-15 00:00 UTC ──")
    dt2 = datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
    report2 = run_full_validation(HAWORTH, dt2)
    _print_report(report2)

    # ── Test 3: Third site ──────────────────────────────────────────
    print("\n── Test 3: de Gerlache Rim 1, 2026-Sep-21 06:00 UTC ──")
    dt3 = datetime(2026, 9, 21, 6, 0, tzinfo=timezone.utc)
    report3 = run_full_validation(DE_GERLACHE_RIM_1, dt3)
    _print_report(report3)

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("VALIDATION SUMMARY")
    print("=" * 72)
    all_passed = report1.all_passed and report2.all_passed and report3.all_passed
    print(f"  Test 1 (Shackleton):  {report1.summary}")
    print(f"  Test 2 (Haworth):     {report2.summary}")
    print(f"  Test 3 (de Gerlache): {report3.summary}")
    print(f"\n  OVERALL: {'ALL PASSED ✓' if all_passed else 'SOME CHECKS FAILED ✗'}")
    print("=" * 72)

    # Dump full JSON for the first report
    print("\n── Full JSON (Test 1) ──")
    print(json.dumps(report1.to_dict(), indent=2))


def _print_report(report):
    print(f"  Site: {report.site_name}")
    print(f"  Time: {report.observation_time}")
    print(f"  Result: {report.summary}")
    for c in report.checks:
        icon = "✓" if c.passed else "✗"
        print(f"    {icon} {c.name}: {c.message}")


if __name__ == "__main__":
    try:
        run_all()
    except (HorizonsConnectionError, HorizonsAPIError) as exc:
        print(f"Live validation could not complete: {exc}", file=sys.stderr)
        print(
            "No celestial results were fabricated or treated as validated. "
            "Run again from a network that can reach the JPL Horizons API.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

