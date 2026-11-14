"""
horizons_client.py — JPL Horizons API Client
=============================================

Builds, sends, and parses JPL Horizons observer-ephemeris queries for
targets (Sun, Earth) as seen from arbitrary lunar surface locations.

Public interface
----------------
    query_body(body_id, body_name, site, dt_utc)  -> CelestialResult
    query_sun(site, dt_utc)                        -> CelestialResult
    query_earth(site, dt_utc)                      -> CelestialResult
    query_site(site, dt_utc)                       -> SiteObservation

Coordinate conventions
----------------------
    - Longitude : East-positive (IAU / Horizons default for the Moon)
    - Latitude  : Selenocentric (south pole ≈ −90°)
    - Altitude  : km above reference ellipsoid
    - Azimuth   : 0° = North, clockwise
    - Elevation : positive above horizon, negative below
    - Time      : UTC

Data provenance
---------------
    Every result returned by this module is derived exclusively from a
    real JPL Horizons API response.  No positions are fabricated.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from astronomy.api.config import (
    ANG_FORMAT,
    CAL_FORMAT,
    COORD_TYPE,
    DEFAULT_QUANTITIES,
    EARTH_ID,
    EPHEM_TYPE,
    EXTRA_PREC,
    HORIZONS_BASE_URL,
    MAX_RETRIES,
    MOON_ID,
    OBSERVER_CENTER_TEMPLATE,
    OUTPUT_FORMAT,
    REQUEST_TIMEOUT_SECONDS,
    SUN_ID,
    TIME_DIGITS,
)
from astronomy.api.exceptions import (
    HorizonsAPIError,
    HorizonsConnectionError,
    HorizonsParseError,
    InvalidCoordinateError,
    InvalidDateError,
)
from astronomy.models.landing_site import (
    CelestialResult,
    LandingSite,
    SiteObservation,
)

logger = logging.getLogger(__name__)

# Body-ID → human-readable name
BODY_NAMES: dict[str, str] = {
    SUN_ID: "Sun",
    EARTH_ID: "Earth",
}


# ═══════════════════════════════════════════════════════════════════════
# 1.  Query-URL builder
# ═══════════════════════════════════════════════════════════════════════

def _build_params(
    body_id: str,
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 m",
    quantities: str = DEFAULT_QUANTITIES,
) -> dict[str, str]:
    """
    Build the query-string parameter dict for a Horizons API request.

    Parameters
    ----------
    body_id   : Horizons ID of the target body ("10" for Sun, "399" for Earth).
    site      : Lunar surface location.
    start_utc : Ephemeris start (UTC).
    stop_utc  : Ephemeris end (UTC).
    step_size : Horizons step size string (default "1 m" = 1 minute).
    quantities: Comma-separated quantity codes (default from config).

    Returns
    -------
    dict suitable for passing as ``params=`` to httpx.get().
    """
    center = OBSERVER_CENTER_TEMPLATE.format(body_id=MOON_ID)

    return {
        "format":      OUTPUT_FORMAT,
        "COMMAND":     f"'{body_id}'",
        "EPHEM_TYPE":  f"'{EPHEM_TYPE}'",
        "CENTER":      f"'{center}'",
        "COORD_TYPE":  f"'{COORD_TYPE}'",
        "SITE_COORD":  f"'{site.site_coord_string}'",
        "START_TIME":  f"'{start_utc.strftime('%Y-%m-%d %H:%M')}'",
        "STOP_TIME":   f"'{stop_utc.strftime('%Y-%m-%d %H:%M')}'",
        "STEP_SIZE":   f"'{step_size}'",
        "QUANTITIES":  f"'{quantities}'",
        "ANG_FORMAT":  f"'{ANG_FORMAT}'",
        "CAL_FORMAT":  f"'{CAL_FORMAT}'",
        "TIME_DIGITS": f"'{TIME_DIGITS}'",
        "EXTRA_PREC":  f"'{EXTRA_PREC}'",
    }


# ═══════════════════════════════════════════════════════════════════════
# 2.  HTTP request with retry
# ═══════════════════════════════════════════════════════════════════════

def _send_request(params: dict[str, str]) -> str:
    """
    Send a GET request to the Horizons API and return the raw text body.

    Raises
    ------
    HorizonsConnectionError : Network / timeout failure.
    HorizonsAPIError        : Non-2xx HTTP status or Horizons error string.
    """
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Horizons request attempt %d/%d  target=%s",
                attempt, MAX_RETRIES, params.get("COMMAND", "?"),
            )
            resp = httpx.get(
                HORIZONS_BASE_URL,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            # ── Check HTTP status ───────────────────────────────────
            if resp.status_code != 200:
                raise HorizonsAPIError(
                    f"Horizons returned HTTP {resp.status_code}",
                    status_code=resp.status_code,
                    body=resp.text,
                )

            body = resp.text

            # ── Horizons sometimes returns 200 but with an error msg ─
            #    (e.g. bad COMMAND value).  Detect this.
            if "$$SOE" not in body and "No ephemeris" in body:
                raise HorizonsAPIError(
                    "Horizons returned an error inside a 200 response",
                    status_code=200,
                    body=body,
                )

            return body

        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("Horizons request timed out (attempt %d)", attempt)
        except httpx.RequestError as exc:
            last_exc = exc
            logger.warning(
                "Horizons connection error (attempt %d): %s", attempt, exc
            )
        except HorizonsAPIError:
            raise  # Don't retry on API-level errors

    # All retries exhausted
    raise HorizonsConnectionError(
        f"Failed to reach Horizons after {MAX_RETRIES} attempts: {last_exc}"
    ) from last_exc


# ═══════════════════════════════════════════════════════════════════════
# 3.  Response parser
# ═══════════════════════════════════════════════════════════════════════

def _safe_float(value: str) -> Optional[float]:
    """Convert a Horizons column value to float, returning None for 'n.a.' etc."""
    value = value.strip()
    if not value or value.lower() in ("n.a.", "n/a", "***", "n.a"):
        return None
    try:
        return float(value)
    except ValueError:
        logger.warning("Could not parse '%s' as float — returning None", value)
        return None


def _extract_ephemeris_block(text: str) -> str:
    """
    Extract the data rows between $$SOE and $$EOE markers.

    Raises
    ------
    HorizonsParseError : If markers are missing.
    """
    soe_match = re.search(r"^\$\$SOE\s*$", text, re.MULTILINE)
    eoe_match = re.search(r"^\$\$EOE\s*$", text, re.MULTILINE)

    if not soe_match or not eoe_match:
        # Try to extract a useful error message from Horizons
        err_lines = [
            line.strip() for line in text.splitlines()
            if "error" in line.lower() or "cannot" in line.lower()
        ]
        hint = "; ".join(err_lines[:3]) if err_lines else "(no error hint found)"
        raise HorizonsParseError(
            f"Horizons response missing $$SOE/$$EOE markers. Hint: {hint}"
        )

    return text[soe_match.end():eoe_match.start()].strip()


def _detect_column_headers(text: str) -> list[str]:
    """
    Read the column-header line(s) that appear just before $$SOE and
    return a normalised list of column labels.

    Horizons prints column headers in the lines immediately preceding
    the ``****...`` separator line and ``$$SOE``.  The format varies
    slightly depending on QUANTITIES, so we parse it dynamically.
    """
    lines = text.splitlines()

    # Find the index of $$SOE
    soe_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == "$$SOE":
            soe_idx = i
            break
    if soe_idx is None:
        raise HorizonsParseError("Cannot find $$SOE for column-header detection")

    # Walk backwards from $$SOE to find the header block.
    # Horizons places a row of asterisks/dashes as a separator, then
    # column headers above that.  We collect the non-blank lines between
    # the separator and the previous blank line.
    header_lines: list[str] = []
    for i in range(soe_idx - 1, max(soe_idx - 15, -1), -1):
        stripped = lines[i].strip()
        if stripped.startswith("*") or stripped.startswith("-"):
            break  # Hit the separator
        if stripped:
            header_lines.insert(0, stripped)
        else:
            break

    # Join header lines and split on whitespace to get column tokens
    raw_header = " ".join(header_lines)
    return raw_header.split()


def _parse_data_row(
    row: str,
    body_id: str,
    body_name: str,
    site: LandingSite,
) -> CelestialResult:
    """
    Parse a single Horizons ephemeris data row into a CelestialResult.

    The column layout depends on QUANTITIES='1,4,10,20,24':
    Typical columns (Horizons text, EXTRA_PREC=YES, ANG_FORMAT=DEG):

        Date__(UT)__HR:MN  R.A._____(ICRF)_____DEC  Azi____(a-app)___Elev
        Illu%  delta  deldot  S-T-O

    Because Horizons uses fixed-width (not delimited) columns,
    and column widths shift with precision settings, we use a
    multi-pass regex strategy instead of positional slicing.
    """
    # Clean up the row — remove leading/trailing whitespace
    row = row.strip()
    if not row:
        raise HorizonsParseError("Empty data row")

    # ── Extract datetime ────────────────────────────────────────────
    # Horizons calendar format: "2026-Mar-01 12:00"  or similar
    dt_match = re.match(
        r"(\d{4}-[A-Za-z]+-\d{1,2}\s+\d{2}:\d{2})", row
    )
    if not dt_match:
        raise HorizonsParseError(f"Cannot parse datetime from row: {row!r}")

    dt_str = dt_match.group(1)
    try:
        dt_utc = datetime.strptime(dt_str, "%Y-%b-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise HorizonsParseError(f"Cannot parse datetime string: {dt_str!r}")

    # ── Extract all numeric / n.a. tokens after the datetime ────────
    remainder = row[dt_match.end():].strip()

    # Remove any flag characters that Horizons appends (single letters
    # like 'r', 'N', 'S', '*', 'm', 'C', etc. that appear between or
    # adjacent to numbers as rise/set/transit markers)
    # We keep 'n.a.' intact, strip isolated single-char flags
    tokens: list[str] = []
    for tok in remainder.split():
        # Skip pure single-character flags (not 'n.a.' fragments)
        if len(tok) == 1 and tok not in (".", "-"):
            continue
        # Skip tokens that are purely flag-like (e.g. "/L", "*m")
        if len(tok) <= 2 and not tok.replace(".", "").replace("-", "").isdigit():
            if tok.lower() not in ("n.a.", "n/a"):
                continue
        tokens.append(tok)

    # ── Map tokens to quantities ────────────────────────────────────
    # Expected token order for QUANTITIES='1,4,10,20,24':
    #   0: RA    1: DEC    2: Azimuth    3: Elevation
    #   4: Illum%    5: delta (range AU or km)    6: deldot (range-rate)
    #   7: S-T-O (phase angle)
    #
    # Horizons may merge 'n.a.' with surrounding spaces, so our token
    # count can vary.  We handle this gracefully.

    def get_token(idx: int) -> Optional[float]:
        if idx < len(tokens):
            return _safe_float(tokens[idx])
        return None

    ra_deg = get_token(0)
    dec_deg = get_token(1)
    azimuth_deg = get_token(2)
    elevation_deg = get_token(3)

    # Illuminated fraction (Horizons returns as percentage, 0-100)
    illum_raw = get_token(4)
    illuminated_fraction = illum_raw / 100.0 if illum_raw is not None else None

    # Range — Horizons observer table returns 'delta' in AU by default.
    # We convert to km (1 AU = 149_597_870.7 km).
    AU_TO_KM = 149_597_870.7
    range_raw = get_token(5)
    range_km: Optional[float] = None
    if range_raw is not None:
        # Heuristic: if the value is < 1000, it's likely in AU.
        # Sun distance ~1 AU, Earth distance ~0.0026 AU.
        # If > 100_000 it's already in km.
        if range_raw < 1000.0:
            range_km = range_raw * AU_TO_KM
        else:
            range_km = range_raw

    # Range-rate (km/s)
    range_rate_km_s = get_token(6)

    # Phase angle (degrees)
    phase_angle_deg = get_token(7)

    return CelestialResult(
        target_body=body_name,
        target_id=body_id,
        site=site,
        datetime_utc=dt_utc,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        range_km=range_km,
        range_rate_km_s=range_rate_km_s,
        illuminated_fraction=illuminated_fraction,
        phase_angle_deg=phase_angle_deg,
    )


def _parse_response(
    text: str,
    body_id: str,
    body_name: str,
    site: LandingSite,
) -> list[CelestialResult]:
    """
    Parse the full Horizons text response into a list of CelestialResult.

    Parameters
    ----------
    text      : Raw Horizons API response body.
    body_id   : Target body ID.
    body_name : Human-readable target name.
    site      : Observer landing site.

    Returns
    -------
    List of one CelestialResult per ephemeris row.

    Raises
    ------
    HorizonsParseError : If the response cannot be parsed.
    """
    block = _extract_ephemeris_block(text)
    results: list[CelestialResult] = []

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            result = _parse_data_row(stripped, body_id, body_name, site)
            results.append(result)
        except HorizonsParseError as exc:
            logger.warning("Skipping unparseable row: %s — %s", stripped, exc)

    if not results:
        raise HorizonsParseError(
            "No data rows could be parsed from the Horizons response"
        )

    return results


# ═══════════════════════════════════════════════════════════════════════
# 4.  Input validators
# ═══════════════════════════════════════════════════════════════════════

def _validate_datetime(dt: datetime) -> datetime:
    """
    Ensure the datetime is timezone-aware UTC and within Horizons' range.

    Horizons supports roughly 1599–2500 AD for major bodies.
    """
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
        logger.info("Naive datetime assumed to be UTC: %s", dt.isoformat())

    year = dt.year
    if year < 1599 or year > 2500:
        raise InvalidDateError(
            f"Date {dt.isoformat()} is outside the Horizons range (1599–2500 AD)"
        )
    return dt


# ═══════════════════════════════════════════════════════════════════════
# 5.  Public API
# ═══════════════════════════════════════════════════════════════════════

def query_body(
    body_id: str,
    body_name: str,
    site: LandingSite,
    dt_utc: datetime,
    step_size: str = "1 m",
    quantities: str = DEFAULT_QUANTITIES,
) -> CelestialResult:
    """
    Query Horizons for one target body as seen from a lunar surface site
    at a specific UTC instant.

    Parameters
    ----------
    body_id   : Horizons body ID  ("10" for Sun, "399" for Earth).
    body_name : Human-readable name ("Sun", "Earth").
    site      : Lunar landing site.
    dt_utc    : Observation time (UTC).
    step_size : Horizons step size (default "1 m").
    quantities: Horizons quantity codes (default from config).

    Returns
    -------
    CelestialResult with the parsed observation data.

    Raises
    ------
    InvalidDateError        : Bad datetime.
    HorizonsConnectionError : Network failure.
    HorizonsAPIError        : API error response.
    HorizonsParseError      : Cannot parse the response.
    """
    dt_utc = _validate_datetime(dt_utc)

    # Single-point workaround: request a 1-step ephemeris
    start = dt_utc
    stop = dt_utc + timedelta(minutes=1)

    params = _build_params(
        body_id=body_id,
        site=site,
        start_utc=start,
        stop_utc=stop,
        step_size=step_size,
        quantities=quantities,
    )

    logger.info(
        "Querying Horizons: %s from %s at %s",
        body_name, site.name, dt_utc.isoformat(),
    )

    raw = _send_request(params)
    results = _parse_response(raw, body_id, body_name, site)

    # Return the first row (closest to the requested instant)
    return results[0]


def query_body_range(
    body_id: str,
    body_name: str,
    site: LandingSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_size: str = "1 h",
    quantities: str = DEFAULT_QUANTITIES,
) -> list[CelestialResult]:
    """
    Query Horizons for a target body over a time range.

    Returns one CelestialResult per time step.
    """
    start_utc = _validate_datetime(start_utc)
    stop_utc = _validate_datetime(stop_utc)

    if stop_utc <= start_utc:
        raise InvalidDateError("stop_utc must be after start_utc")

    params = _build_params(
        body_id=body_id,
        site=site,
        start_utc=start_utc,
        stop_utc=stop_utc,
        step_size=step_size,
        quantities=quantities,
    )

    logger.info(
        "Querying Horizons range: %s from %s (%s → %s, step %s)",
        body_name, site.name,
        start_utc.isoformat(), stop_utc.isoformat(), step_size,
    )

    raw = _send_request(params)
    return _parse_response(raw, body_id, body_name, site)


def query_sun(site: LandingSite, dt_utc: datetime) -> CelestialResult:
    """Query the Sun's position from a lunar surface site at a UTC instant."""
    return query_body(SUN_ID, "Sun", site, dt_utc)


def query_earth(site: LandingSite, dt_utc: datetime) -> CelestialResult:
    """Query the Earth's position from a lunar surface site at a UTC instant."""
    return query_body(EARTH_ID, "Earth", site, dt_utc)


def query_site(site: LandingSite, dt_utc: datetime) -> SiteObservation:
    """
    Query both Sun and Earth from a lunar surface site at a UTC instant.

    Returns a SiteObservation bundle.  If one query fails, the
    corresponding field is None and a warning is logged (the other
    query result is still returned).
    """
    dt_utc = _validate_datetime(dt_utc)
    obs = SiteObservation(site=site, datetime_utc=dt_utc)

    # Query Sun
    try:
        obs.sun = query_sun(site, dt_utc)
    except Exception as exc:
        logger.error("Sun query failed for %s: %s", site.name, exc)

    # Query Earth
    try:
        obs.earth = query_earth(site, dt_utc)
    except Exception as exc:
        logger.error("Earth query failed for %s: %s", site.name, exc)

    return obs


# ═══════════════════════════════════════════════════════════════════════
# 6.  Diagnostic / raw access
# ═══════════════════════════════════════════════════════════════════════

def get_raw_response(
    body_id: str,
    site: LandingSite,
    dt_utc: datetime,
) -> str:
    """
    Return the raw text response from Horizons without parsing.

    Useful for debugging column layouts or investigating parse failures.
    """
    dt_utc = _validate_datetime(dt_utc)
    start = dt_utc
    stop = dt_utc + timedelta(minutes=1)
    params = _build_params(body_id, site, start, stop)
    return _send_request(params)
