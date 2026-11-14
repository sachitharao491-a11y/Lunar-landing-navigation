
# Lunar Landing Project — Data Sources

## 1. JPL Horizons
Purpose: Obtain celestial positions.
Used for:
- Sun position
- Earth position
- Time-based position calculations

Status: To be explored

## 2. NASA SPICE / SpiceyPy
Purpose: Perform accurate geometry calculations.
Used for:
- Coordinate transformations
- Celestial positions
- Observer geometry

Status: To be explored

## 3. LOLA
Purpose: Obtain lunar terrain elevation.
Used for:
- Terrain visualization
- Horizon obstruction
- Terrain-aware visibility

Status: To be explored

## Important assumptions
- Geometric visibility is not terrain-aware visibility.
- Mock values must never be presented as verified NASA data.
- Simplified sunlight estimates are not engineering-grade power predictions.
