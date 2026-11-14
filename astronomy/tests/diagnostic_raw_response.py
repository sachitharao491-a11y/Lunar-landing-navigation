"""
Phase 2 diagnostic: Fetch BOTH Sun and Earth raw responses, then test
the full parsed pipeline.
"""

import sys
sys.path.insert(0, r"c:\Users\Sachith A Rao\OneDrive\Desktop\NASA hackathon preparation")

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from astronomy.api.horizons_client import get_raw_response, query_site
from astronomy.models.landing_site import SHACKLETON_RIM
from datetime import datetime, timezone
import json

dt = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

# ── Raw Earth response ──────────────────────────────────
print("=" * 72)
print("RAW HORIZONS RESPONSE — Earth from Shackleton Rim")
print("=" * 72)
raw_earth = get_raw_response("399", SHACKLETON_RIM, dt)
# Print just the $$SOE block
for line in raw_earth.splitlines():
    if "$$SOE" in line or "$$EOE" in line or ("2026-Mar" in line):
        print(line)
    if "Date__" in line:
        print(line)

# ── Full parsed pipeline ────────────────────────────────
print("\n" + "=" * 72)
print("PARSED RESULTS — query_site()")
print("=" * 72)
obs = query_site(SHACKLETON_RIM, dt)
print(json.dumps(obs.to_dict(), indent=2))
