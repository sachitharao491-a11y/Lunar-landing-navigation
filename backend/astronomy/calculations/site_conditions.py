"""Derived surface visibility and solar irradiance for a lunar observation."""

from __future__ import annotations

import math

from astronomy.models.landing_site import CelestialResult

# NASA's commonly used nominal total solar irradiance at 1 AU. Actual TSI varies.
REFERENCE_TSI_W_M2 = 1361.0
AU_KM = 149_597_870.7
TSI_REFERENCE = "NASA GSFC solar irradiance overview; nominal TSI 1361 W/m²"
TSI_SOURCE_URL = "https://earth.gsfc.nasa.gov/climate/projects/solar-irradiance/science"


def derive_site_conditions(sun: CelestialResult, earth: CelestialResult) -> dict:
    """Derive geometric Earth line of sight and nominal direct solar irradiance.

    Earth status uses the Horizons apparent center elevation and the geometric
    local horizon. It does not establish RF link performance.
    Solar flux scales nominal 1 AU TSI by the inverse square of Horizons range;
    horizontal-plane irradiance applies the local elevation cosine factor.
    Neither value models terrain, surface slope, or time-varying TSI.
    """
    earth_visible = earth.is_above_horizon
    earth_elevation = earth.elevation_deg

    solar_distance = sun.range_km
    sun_elevation = sun.elevation_deg
    normal_irradiance = None
    horizontal_irradiance = None
    if solar_distance is not None and solar_distance > 0 and sun_elevation is not None:
        top_of_surface_flux = REFERENCE_TSI_W_M2 * (AU_KM / solar_distance) ** 2
        if sun_elevation > 0:
            normal_irradiance = top_of_surface_flux
            horizontal_irradiance = top_of_surface_flux * math.sin(math.radians(sun_elevation))
        else:
            normal_irradiance = 0.0
            horizontal_irradiance = 0.0

    return {
        "earth_visibility": {
            "earth_center_above_geometric_horizon": earth_visible,
            "geometric_line_of_sight": earth_visible,
            "earth_elevation_deg": earth_elevation,
            "radio_link_assessment": "not_assessed",
            "radio_link_note": "Requires antenna, frequency, power, pointing, and link-budget data.",
        },
        "solar_irradiance": {
            "sun_center_above_geometric_horizon": sun.is_above_horizon,
            "sun_distance_km": solar_distance,
            "direct_normal_w_m2": normal_irradiance,
            "horizontal_surface_w_m2": horizontal_irradiance,
            "reference_tsi_w_m2": REFERENCE_TSI_W_M2,
            "reference_source": TSI_REFERENCE,
            "reference_source_url": TSI_SOURCE_URL,
            "method": "Nominal TSI scaled by inverse-square Sun distance; horizontal plane multiplied by sin(elevation).",
            "limitations": "Estimate; TSI variability, local terrain, slopes, and shadows are not modeled.",
        },
    }

