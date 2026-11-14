"""
Astronomy and Scientific Calculations Module
=============================================
Member 1 — Lunar Landing Intelligence Platform

This package provides functions to determine the positions of the Sun and Earth
as observed from a selected lunar south-pole landing site at a specified UTC
date/time.

Data sources:
    - JPL Horizons API (primary — ephemeris queries)
    - NASA SPICE / SpiceyPy (supplementary — reference-frame transformations)

Coordinate conventions:
    - Lunar longitude: East-positive (IAU convention, matches Horizons)
    - Lunar latitude : Planetocentric (selenocentric)
    - Azimuth        : North = 0°, measured clockwise through East
    - Elevation      : Positive above the local horizon, negative below
    - Time           : UTC (converted internally to TDB where needed)
"""

__version__ = "0.1.0"

