"""
Horizons API configuration constants.

These values are used by horizons_client.py to construct queries.
They are centralised here so that the entire module can be reconfigured
from a single file.
"""

# ── API Endpoint ────────────────────────────────────────────────────────
HORIZONS_BASE_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"

# ── Target Body IDs ─────────────────────────────────────────────────────
SUN_ID = "10"
EARTH_ID = "399"
MOON_ID = "301"

# ── Observer Configuration ──────────────────────────────────────────────
# CENTER format: 'coord@<body_id>'  — user-defined coordinate on a body
OBSERVER_CENTER_TEMPLATE = "coord@{body_id}"

# Coordinate type for surface locations (longitude, latitude, altitude)
COORD_TYPE = "GEODETIC"

# ── Ephemeris Type ──────────────────────────────────────────────────────
EPHEM_TYPE = "OBSERVER"

# ── Default Quantities ──────────────────────────────────────────────────
# 1  = Astrometric RA & DEC
# 4  = Apparent azimuth & elevation
# 10 = Illuminated fraction
# 20 = Observer range & range-rate
# 24 = Sun-Target-Observer phase angle
DEFAULT_QUANTITIES = "1,4,10,20,24"

# ── Output Formatting ──────────────────────────────────────────────────
ANG_FORMAT = "DEG"          # Decimal degrees (not DMS)
CAL_FORMAT = "CAL"          # Calendar date in output
TIME_DIGITS = "MINUTES"     # Time precision
EXTRA_PREC = "YES"          # Additional decimal places
OUTPUT_FORMAT = "text"      # Horizons text format

# ── Network ─────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2

# ── Validation Bounds ──────────────────────────────────────────────────
LONGITUDE_MIN = -180.0
LONGITUDE_MAX = 360.0       # Horizons accepts 0-360 OR -180 to +180
LATITUDE_MIN = -90.0
LATITUDE_MAX = 90.0
ALTITUDE_MIN_KM = -10.0     # Slightly below surface for crater floors
ALTITUDE_MAX_KM = 50.0      # Well above any lunar feature

