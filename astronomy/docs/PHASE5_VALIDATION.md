# Phase 5: scientific validation status

## Scope

This phase checks whether the module's observations are consistent with an
independent reference. The existing `scientific_validation.py` checks useful
physical bounds and continuity, but these checks alone do **not** validate the
azimuth/elevation calculation or prove that the response parser selected the
right fields. A repeated call through the same client is not an independent
reference.

## Horizons configuration to compare

For each target, configure a Horizons **Observer Table** with:

| Parameter | Value |
| --- | --- |
| Target | Sun `10` or Earth `399` |
| Center | `coord@301` (user coordinate on the Moon) |
| Coordinate type | Geodetic (`GEODETIC`) |
| Site coordinates | east longitude, latitude, altitude in km; e.g. `129,-89.68,0` |
| Ephemeris type | Observer |
| Interval | requested UTC instant to one minute later, step `1 m` |
| Quantities | at minimum `4,20`; optionally `1,10,24` for diagnostics |
| Angle format | decimal degrees |

The module currently requests `QUANTITIES='1,4,10,20,24'`. Compare the printed
observer-table quantity 4 (`AZ`, `EL`) and 20 (observer range/range rate) with
the corresponding module result. Compare timestamps exactly. Quantity 4 is
Horizons' apparent, airless topocentric direction (light-time, aberration and
other apparent-place corrections included); it should not be described as a
pure geometric direction. For a geometric-only comparison, request geometric
vectors or configure the reference calculation to match the same corrections.

The official manual describes observer tables as observer-dependent and
quantity 4 as topocentric apparent azimuth/elevation. It also specifies that
non-Earth body coordinates use IAU geodetic/planetographic conventions (the
Moon uses the mean Earth of DE421). See the [Horizons manual](https://ssd.jpl.nasa.gov/horizons/manual.html)
and [Horizons API documentation](https://ssd-api.jpl.nasa.gov/doc/horizons.html).

## Independent calculation

For a stronger check than using the Horizons web interface and API (which share
the same ephemeris service), compute the target direction independently with
SPICE: obtain target and lunar observer states at matched epochs, transform
through the selected lunar body-fixed frame using the matching lunar frame and
orientation kernels, then project the topocentric vector onto local north,
east, and up axes. Match the Horizons light-time/aberration convention before
comparing apparent directions. Document kernel names and versions, frame,
observer altitude, time scale, and correction flags. A comparison of only
geometric SPICE vectors to apparent Horizons angles is not apples-to-apples.

## Live results (2026-11-11)

The module was queried live, then separately queried through the official
Horizons API using the same target, site, UTC interval and observer, but only
quantities `4,20` (rather than the module's `1,4,10,20,24`). The API returned
airless apparent topocentric values as expected. Values below are the 12:00 UT
row; the direct reference output is rounded to six decimals for angles and
the API's displayed precision for range.

| Target | Module azimuth | Reference azimuth | Module elevation | Reference elevation | Module range km | Reference range km |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sun | 259.853369911° | 259.853370° | -0.124839033° | -0.124839° | 148,567,477.8270 | 148,567,477.83 |
| Earth | 235.077998890° | 235.077999° | 2.190169583° | 2.190170° | 375,837.2155 | 375,837.21546 |

Differences are consistent with reference display rounding (less than
0.000001° in the angles and 0.004 km in range). This validates that, for this
case, the module's request configuration and parser reproduce a separately
configured Horizons observer table. It is not an independent ephemeris source:
both queries use JPL Horizons.

The live `python -m astronomy.validation.run_validation` run also completed all
three configured cases (Shackleton, Haworth, and de Gerlache Rim 1); each
reported 12/12 checks passed, with zero errors and warnings. These bounds and
continuity checks are supporting plausibility checks, not an independent
SPICE calculation.

The initial sandboxed run failed with socket access denied (`WinError 10013`);
the live runs succeeded when network access was allowed. No mock or fabricated
values were used.

## Known validation gaps

- Existing distance bounds, legal angle ranges, and temporal smoothness checks
  are plausibility checks, not cross-validation.
- The separately configured Horizons comparison covers one site/time. A
  matched SPICE computation with documented kernels and correction settings
  remains a stronger independent cross-check and has not been performed.
- Lunar site input conventions must be reconciled with the source coordinates:
  Horizons expects east-positive geodetic/planetographic coordinates, while
  the module's model docstring currently calls latitude planetocentric. Do not
  assume those definitions are interchangeable for high-accuracy work.
- Horizons azimuth is defined relative to local north and elevation to the
  plane perpendicular to local zenith; neither represents terrain occlusion.
- Geometric horizon visibility, apparent direction, and terrain-aware
  visibility are separate outputs and need separate validation criteria.
