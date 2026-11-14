# PHASE 1 — JPL Horizons API Investigation

> **Status:** Complete  
> **Author:** Member 1 (Astronomy & Scientific Calculations)  
> **Date:** 2026-11-10

---

## 1. What is JPL Horizons?

JPL Horizons is a solar-system ephemeris service operated by NASA's Jet Propulsion
Laboratory. It computes positions, velocities, and derived geometric quantities for
solar-system objects (planets, moons, spacecraft, asteroids, comets) as seen from any
observer location — including arbitrary coordinates on the surface of the Moon.

**API endpoint:**

```
https://ssd.jpl.nasa.gov/api/horizons.api
```

The API accepts HTTP GET requests with query-string parameters and returns plain-text
ephemeris tables.  No API key is required.

---

## 2. Our Goal

For a given **lunar surface location** (latitude, longitude) and **UTC date/time**,
retrieve the **Sun** and **Earth** positions (azimuth, elevation, distance) as they
would be observed from that point on the Moon.

---

## 3. Core API Parameters

### 3.1 Identifying the target body (`COMMAND`)

| Target | Horizons ID | `COMMAND` value |
|--------|-------------|-----------------|
| Sun    | `10`        | `'10'`          |
| Earth  | `399`       | `'399'`         |

### 3.2 Setting the observer to a lunar surface point

This is the critical configuration.  We are **not** observing from Earth; we are
observing from a point on the Moon's surface.

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `CENTER` | `'coord@301'` | Observer is at a user-defined coordinate on body 301 (Moon) |
| `COORD_TYPE` | `'GEODETIC'` | Coordinates are (longitude, latitude, altitude) |
| `SITE_COORD` | `'<lon>,<lat>,<alt>'` | East-positive longitude (°), latitude (°), altitude above reference ellipsoid (km) |

**Example for the Shackleton crater rim (≈ 89.68° S, 129.0° E):**

```
CENTER      = 'coord@301'
COORD_TYPE  = 'GEODETIC'
SITE_COORD  = '129.0,-89.68,0'
```

### 3.3 Longitude convention (critical!)

Horizons uses **East-positive** longitude for the Moon (IAU convention):

| Direction | Sign |
|-----------|------|
| East longitude | Positive (+) |
| West longitude | Negative (−) |

**This must be enforced in our code.**  A site at 45° W must be passed as `−45.0`.

### 3.4 Latitude convention

Standard planetocentric (selenocentric) latitude:

| Location | Range |
|----------|-------|
| North pole | +90° |
| Equator | 0° |
| South pole | −90° |

South-pole landing sites will have latitudes near **−89° to −90°**.

### 3.5 Altitude

Altitude is in **kilometres** above the Moon's reference ellipsoid.  For a surface
landing site with no significant elevation data, use `0` km.

### 3.6 Ephemeris type (`EPHEM_TYPE`)

```
EPHEM_TYPE = 'OBSERVER'
```

This produces a topocentric observer table — the standard table for "what does an
observer at this location see?"

### 3.7 Time parameters

| Parameter | Format | Example |
|-----------|--------|---------|
| `START_TIME` | `'YYYY-MM-DD HH:MM'` | `'2026-03-01 12:00'` |
| `STOP_TIME` | `'YYYY-MM-DD HH:MM'` | `'2026-03-01 12:01'` |
| `STEP_SIZE` | `'N m'`, `'N h'`, `'N d'` | `'1 m'` (1 minute) |

For a single instant, set `STOP_TIME` one minute after `START_TIME` and
`STEP_SIZE = '1 m'`.  Horizons does not support a true "single-point" query in the
URL API; the workaround is a 1-step ephemeris.

### 3.8 Quantities we need (`QUANTITIES`)

| Code | Quantity | Why we need it |
|------|----------|---------------|
| `4` | **Apparent azimuth & elevation** | Primary output — where is the target in the local sky? |
| `20` | **Observer range & range-rate** | Distance from observer to target (km, km/s) |
| `1` | **Astrometric RA & DEC** | Cross-check / debugging reference frame |
| `10` | **Illuminated fraction** | Useful for Earth phase as seen from Moon |
| `24` | **Sun-Target-Observer phase angle** | Lighting geometry |

Our primary request:

```
QUANTITIES = '1,4,10,20,24'
```

### 3.9 Output formatting

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `format` | `'text'` | Plain-text response (easier to parse than JSON for Horizons) |
| `ANG_FORMAT` | `'DEG'` | Angles in decimal degrees (not DMS) |
| `CAL_FORMAT` | `'CAL'` | Calendar date format in output |
| `TIME_DIGITS` | `'MINUTES'` | Time precision |
| `EXTRA_PREC` | `'YES'` | Higher decimal precision in output columns |

---

## 4. Complete Example Queries

### 4.1 Sun as seen from Shackleton crater rim

```
https://ssd.jpl.nasa.gov/api/horizons.api?format=text
  &COMMAND='10'
  &EPHEM_TYPE='OBSERVER'
  &CENTER='coord@301'
  &COORD_TYPE='GEODETIC'
  &SITE_COORD='129.0,-89.68,0'
  &START_TIME='2026-03-01 12:00'
  &STOP_TIME='2026-03-01 12:01'
  &STEP_SIZE='1 m'
  &QUANTITIES='1,4,10,20,24'
  &ANG_FORMAT='DEG'
  &CAL_FORMAT='CAL'
  &EXTRA_PREC='YES'
```

(URL is shown with line breaks for readability; the actual request is a single line.)

### 4.2 Earth as seen from Shackleton crater rim

```
https://ssd.jpl.nasa.gov/api/horizons.api?format=text
  &COMMAND='399'
  &EPHEM_TYPE='OBSERVER'
  &CENTER='coord@301'
  &COORD_TYPE='GEODETIC'
  &SITE_COORD='129.0,-89.68,0'
  &START_TIME='2026-03-01 12:00'
  &STOP_TIME='2026-03-01 12:01'
  &STEP_SIZE='1 m'
  &QUANTITIES='1,4,10,20,24'
  &ANG_FORMAT='DEG'
  &CAL_FORMAT='CAL'
  &EXTRA_PREC='YES'
```

---

## 5. What Horizons Returns

### 5.1 Azimuth definition

- **0°** = North (direction of the Moon's north pole projected onto the local horizon)
- Measured **clockwise**: East = 90°, South = 180°, West = 270°

### 5.2 Elevation definition

- **0°** = local geometric horizon (perpendicular to the local zenith vector)
- **+90°** = zenith (straight up from the surface)
- **−90°** = nadir
- Positive elevation → target is above the horizon
- Negative elevation → target is below the horizon

### 5.3 No atmospheric refraction

The Moon has no atmosphere.  Horizons automatically sets refraction to **0.0** for
any non-Earth observer.  The returned azimuth and elevation are therefore **airless
apparent** values:

- Corrected for light-time
- Corrected for stellar aberration
- Corrected for gravitational light deflection
- **Not** corrected for atmospheric refraction (none exists)

### 5.4 Range

The observer-to-target range is returned in **kilometres** (or AU depending on the
default).  We will parse whichever unit Horizons provides and normalise to km.

---

## 6. Quantities Suppressed or Modified on the Moon

Because the observer is not on Earth, several Horizons quantities behave differently:

| Quantity | Earth observer | Lunar observer |
|----------|---------------|----------------|
| Atmospheric refraction | Applied | **Zero** — no atmosphere |
| Airmass / extinction | Computed | **Suppressed** (`n.a.`) |
| Moonlight sky background | Computed | **N/A** — Earth becomes the interfering body |
| Apparent RA/DEC origin | Earth equinox | Earth equinox of J2000 but DEC uses Moon's true equator-of-date |
| Visual magnitude | Includes extinction | **No extinction correction** |

**Key insight:**  For a lunar observer, the Earth replaces the Moon as the
"visually interfering body."  Quantities describing the interfering body (angular
separation, illumination, obstruction) will report Earth's properties instead of
the Moon's.

---

## 7. Lunar South-Pole Candidate Landing Sites

These are the reference sites we will use for development and testing:

| Site name | Latitude (°) | Longitude (°E) | Notes |
|-----------|-------------|-----------------|-------|
| Peak near Shackleton | −89.68 | +129.0 | Near the rim of Shackleton crater |
| Connecting Ridge | −89.45 | −136.0 | Between Shackleton and de Gerlache |
| Connecting Ridge Extension | −89.30 | −150.0 | Extended ridge area |
| de Gerlache Rim 1 | −88.50 | −68.0 | Western rim of de Gerlache |
| de Gerlache Rim 2 | −88.71 | −64.0 | Eastern rim of de Gerlache |
| Haworth | −87.45 | −5.0 | Haworth crater region |

All coordinates are approximate centroids of NASA Artemis III candidate landing
regions (each region spans roughly 15 × 15 km).

---

## 8. When Is SPICE Needed Instead of Horizons?

Horizons is sufficient for:

- ✅ Sun and Earth azimuth & elevation from a lunar surface point
- ✅ Range and range-rate
- ✅ Illuminated fraction and phase angle
- ✅ Time-series ephemerides (multi-step)

SPICE may be needed for:

- 🔶 Sub-second time resolution or real-time interpolation
- 🔶 Custom coordinate transformations (e.g., body-fixed to topocentric if we
  implement our own geometry instead of relying on Horizons Quantity 4)
- 🔶 Terrain-aware horizon calculations (combine SPICE geometry with LOLA elevation
  data)
- 🔶 Offline/cached computation without network access
- 🔶 Spacecraft trajectory planning (beyond our current scope)

**Decision:** Start with Horizons API exclusively.  Introduce SPICE only if a
specific calculation cannot be achieved through Horizons, or if offline operation
becomes a requirement.

---

## 9. API Limitations and Constraints

| Limitation | Detail |
|------------|--------|
| **Rate limiting** | No published rate limit, but JPL asks users not to submit excessive automated queries.  We must implement caching. |
| **No JSON output for ephemeris** | The `format=json` option returns metadata as JSON but the ephemeris table itself is plain text inside a `"result"` string. |
| **Single-point workaround** | No single-instant query; use a 1-step ephemeris. |
| **Date range** | Typically 1599 AD to 2500 AD for major bodies; well within our needs. |
| **Network dependency** | Every query requires internet access — we need robust error handling and optional caching. |
| **Body-code sensitivity** | Must use correct IDs: Sun = `10`, Earth = `399`, Moon = `301`. |

---

## 10. Response Parsing Strategy

The Horizons text response contains:

1. **Header** — metadata, parameter echo, column labels
2. **`$$SOE`** marker — Start Of Ephemeris
3. **Data rows** — whitespace-delimited columns
4. **`$$EOE`** marker — End Of Ephemeris
5. **Footer** — additional notes

Our parser must:

1. Find the text between `$$SOE` and `$$EOE`.
2. Split each row by whitespace / fixed-width columns.
3. Map column positions to quantity names using the column header.
4. Convert strings to floats (handle `n.a.` gracefully).

---

## 11. Error Handling Requirements

| Scenario | Expected behaviour |
|----------|--------------------|
| Network unreachable | Raise `ConnectionError` with clear message |
| Horizons returns HTTP 4xx/5xx | Raise `HorizonsAPIError` with status code and body |
| Invalid coordinates (lat > 90, etc.) | Validate before sending; raise `ValueError` |
| Date out of range | Validate before sending; raise `ValueError` |
| Response missing `$$SOE`/`$$EOE` | Raise `HorizonsParseError` |
| `n.a.` in a numeric field | Return `None` for that field, log a warning |

---

## 12. Summary of Verified Assumptions

| # | Assumption | Verified? |
|---|-----------|-----------|
| 1 | Horizons supports arbitrary coordinates on the Moon via `coord@301` | ✅ Yes |
| 2 | `COORD_TYPE='GEODETIC'` with `SITE_COORD='lon,lat,alt'` works for the Moon | ✅ Yes |
| 3 | Longitude is East-positive for the Moon in Horizons | ✅ Yes |
| 4 | Quantity `4` returns apparent azimuth & elevation for non-Earth observers | ✅ Yes |
| 5 | Atmospheric refraction is zero for lunar observers | ✅ Yes |
| 6 | No API key is required | ✅ Yes |
| 7 | The API uses plain-text output with `$$SOE`/`$$EOE` delimiters | ✅ Yes |
| 8 | Sun = `10`, Earth = `399`, Moon = `301` | ✅ Yes |

---

## 13. Next Step — PHASE 2

Implement `astronomy/api/horizons_client.py`:

- Build parameterised query URLs
- Send requests via `httpx`
- Parse `$$SOE`/`$$EOE` text blocks
- Return structured Python objects
- Handle all error scenarios from §11

