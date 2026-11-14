"""FastAPI endpoints for live lunar-site Sun and Earth observations.

Run from the repository root with:
    uvicorn astronomy.web.app:app --reload
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from astronomy.api.exceptions import (
    HorizonsAPIError,
    HorizonsConnectionError,
    HorizonsParseError,
    InvalidCoordinateError,
    InvalidDateError,
)
from astronomy.api.horizons_client import query_earth, query_sun
from astronomy.calculations.site_conditions import derive_site_conditions
from astronomy.models.landing_site import LandingSite

app = FastAPI(
    title="Lunar Landing Astronomy API",
    description=(
        "Sun and Earth observer geometry from a lunar surface location. "
        "Azimuth/elevation are airless apparent Horizons quantities; "
        "visibility is geometric and does not include terrain obstruction."
    ),
    version="0.1.0",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MOON_MODEL_PATH = PROJECT_ROOT / "moon_small.glb"
MOON_VIEWER_PATH = Path(__file__).with_name("moon_viewer.html")


@app.get("/moon", include_in_schema=False)
def moon_viewer() -> FileResponse:
    """Interactive Moon model with a marker for entered selenographic coordinates."""
    return FileResponse(MOON_VIEWER_PATH, media_type="text/html")


@app.get("/moon_small.glb", include_in_schema=False)
def moon_model() -> FileResponse:
    """Serve the NASA Moon model used by the interactive viewer."""
    return FileResponse(MOON_MODEL_PATH, media_type="model/gltf-binary")


class ObservationRequest(BaseModel):
    """One observation request. Longitude is east-positive; altitude is km."""

    model_config = ConfigDict(extra="forbid")

    site_name: str = Field(default="User site", min_length=1, max_length=100)
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg_east: float = Field(ge=-180, le=360)
    altitude_km: float = Field(default=0.0, ge=-10, le=50)
    datetime_utc: datetime

    @field_validator("site_name")
    @classmethod
    def site_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("site_name must not be blank")
        return value

    @field_validator("datetime_utc")
    @classmethod
    def require_timezone_and_normalize_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime_utc must include a UTC offset, such as Z")
        return value.astimezone(timezone.utc)


class SiteResponse(BaseModel):
    name: str
    latitude_deg: float
    longitude_deg_east: float
    altitude_km: float


class BodyResponse(BaseModel):
    target_body: str
    target_id: str
    site: SiteResponse
    datetime_utc: str
    azimuth_deg: Optional[float]
    elevation_deg: Optional[float]
    ra_deg: Optional[float]
    dec_deg: Optional[float]
    range_km: Optional[float]
    range_rate_km_s: Optional[float]
    illuminated_fraction: Optional[float]
    phase_angle_deg: Optional[float]
    is_above_horizon: Optional[bool]


class EarthVisibilityResponse(BaseModel):
    earth_center_above_geometric_horizon: Optional[bool]
    geometric_line_of_sight: Optional[bool]
    earth_elevation_deg: Optional[float]
    radio_link_assessment: str
    radio_link_note: str


class SolarIrradianceResponse(BaseModel):
    sun_center_above_geometric_horizon: Optional[bool]
    sun_distance_km: Optional[float]
    direct_normal_w_m2: Optional[float]
    horizontal_surface_w_m2: Optional[float]
    reference_tsi_w_m2: float
    reference_source: str
    reference_source_url: str
    method: str
    limitations: str


class ObservationResponse(BaseModel):
    site: SiteResponse
    datetime_utc: str
    sun: BodyResponse
    earth: BodyResponse
    earth_visibility: EarthVisibilityResponse
    solar_irradiance: SolarIrradianceResponse
    data_source: str = "JPL Horizons API"
    position_type: str = "airless apparent observer quantities"
    visibility_scope: str = "geometric; terrain obstruction not included"


class BatchObservationRequest(BaseModel):
    """A bounded collection of site/time observations (at most 10)."""

    model_config = ConfigDict(extra="forbid")

    observations: list[ObservationRequest] = Field(min_length=1, max_length=10)


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    """Liveness check; does not make a network request to Horizons."""
    return {"status": "ok", "upstream": "not_checked"}


@app.post(
    "/v1/observation",
    response_model=ObservationResponse,
    tags=["observations"],
    summary="Get Sun and Earth geometry from a lunar site",
)
def create_observation(request: ObservationRequest) -> dict:
    """Query both targets for one site and one timezone-aware instant."""
    site = LandingSite(
        name=request.site_name.strip(),
        latitude=request.latitude_deg,
        longitude=request.longitude_deg_east,
        altitude_km=request.altitude_km,
    )
    try:
        sun = query_sun(site, request.datetime_utc)
        earth = query_earth(site, request.datetime_utc)
    except (InvalidCoordinateError, InvalidDateError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HorizonsConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (HorizonsAPIError, HorizonsParseError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "site": {
            "name": site.name,
            "latitude_deg": site.latitude,
            "longitude_deg_east": site.longitude,
            "altitude_km": site.altitude_km,
        },
        "datetime_utc": request.datetime_utc.isoformat(),
        "sun": sun.to_dict(),
        "earth": earth.to_dict(),
        **derive_site_conditions(sun, earth),
    }


@app.post(
    "/v1/observations/batch",
    response_model=list[ObservationResponse],
    tags=["observations"],
    summary="Get observations for multiple sites and/or dates",
)
def create_observations_batch(request: BatchObservationRequest) -> list[dict]:
    """Run up to ten independent observation requests in one integration call.

    Requests execute sequentially to keep upstream load predictable. If one
    Horizons query fails, the endpoint returns that request's mapped error.
    """
    return [create_observation(item) for item in request.observations]
