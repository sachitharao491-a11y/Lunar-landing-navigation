import type { DataSource, Observation, ObservationLocation, Site, TerrainAnalysis, TerrainCatalog } from "../types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    });
  } catch {
    throw new ApiError("The backend could not be reached. Check that the API server is running.");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
    } catch { /* Keep the status message when the server did not return JSON. */ }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("The backend returned a response that was not valid JSON.", response.status);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function nullableNumber(value: unknown): value is number | null {
  return value === null || requiredNumber(value);
}

function nullableBoolean(value: unknown): value is boolean | null {
  return value === null || typeof value === "boolean";
}

function parseSite(value: unknown): Site {
  if (!isRecord(value) || !requiredNumber(value.id) || typeof value.name !== "string" ||
      !["landing", "psr", "landmark"].includes(String(value.kind)) ||
      !requiredNumber(value.lat) || !requiredNumber(value.lon) || typeof value.source !== "string") {
    throw new ApiError("The site catalog response did not match the expected API shape.");
  }
  return value as unknown as Site;
}

function parseObservation(value: unknown): Observation {
  if (!isRecord(value) || !isRecord(value.site) || !isRecord(value.sun) || !isRecord(value.earth) ||
      !isRecord(value.earth_visibility) || !isRecord(value.solar_irradiance) || typeof value.datetime_utc !== "string" ||
      typeof value.data_source !== "string" || typeof value.position_type !== "string" || typeof value.visibility_scope !== "string") {
    throw new ApiError("The astronomy response did not match the expected API shape.");
  }
  const validSite = (site: Record<string, unknown>) => typeof site.name === "string" &&
    requiredNumber(site.latitude_deg) && requiredNumber(site.longitude_deg_east) && requiredNumber(site.altitude_km);
  const validBody = (body: Record<string, unknown>) => typeof body.target_body === "string" &&
    typeof body.target_id === "string" && typeof body.datetime_utc === "string" &&
    isRecord(body.site) && validSite(body.site) &&
    [body.azimuth_deg, body.elevation_deg, body.ra_deg, body.dec_deg, body.range_km, body.range_rate_km_s,
      body.illuminated_fraction, body.phase_angle_deg].every(nullableNumber) && nullableBoolean(body.is_above_horizon);
  const visibility = value.earth_visibility;
  const irradiance = value.solar_irradiance;
  if (!validSite(value.site) || !validBody(value.sun) || !validBody(value.earth) ||
      !nullableBoolean(visibility.earth_center_above_geometric_horizon) ||
      !nullableBoolean(visibility.geometric_line_of_sight) || !nullableNumber(visibility.earth_elevation_deg) ||
      typeof visibility.radio_link_assessment !== "string" || typeof visibility.radio_link_note !== "string" ||
      !nullableBoolean(irradiance.sun_center_above_geometric_horizon) ||
      !nullableNumber(irradiance.sun_distance_km) || !nullableNumber(irradiance.direct_normal_w_m2) ||
      !nullableNumber(irradiance.horizontal_surface_w_m2) || !requiredNumber(irradiance.reference_tsi_w_m2) ||
      typeof irradiance.reference_source !== "string" || typeof irradiance.reference_source_url !== "string" ||
      typeof irradiance.method !== "string" || typeof irradiance.limitations !== "string") {
    throw new ApiError("The astronomy response contained fields with unexpected types.");
  }
  return value as unknown as Observation;
}

export async function getSites(): Promise<Site[]> {
  const value: unknown = await request("/api/sites");
  if (!Array.isArray(value)) throw new ApiError("The site catalog response was not a list.");
  return value.map(parseSite);
}

export async function getDataSources(): Promise<DataSource[]> {
  const value: unknown = await request("/api/datasets");
  if (!Array.isArray(value) || !value.every((row) => isRecord(row) && typeof row.name === "string")) {
    throw new ApiError("The data-source response did not match the expected API shape.");
  }
  return value as DataSource[];
}

export async function getTerrainCatalog(): Promise<TerrainCatalog> {
  const value: unknown = await request("/api/analysis/datasets");
  if (!isRecord(value) || !Array.isArray(value.sites)) throw new ApiError("The terrain catalog response did not match the expected API shape.");
  return value as unknown as TerrainCatalog;
}

export function locationFromSite(site: Site): ObservationLocation {
  return {
    site_name: site.name,
    latitude_deg: site.lat,
    longitude_deg_east: site.lon,
    altitude_km: 0,
  };
}

function observationRequest(location: ObservationLocation, datetimeUtc: string) {
  return {
    ...location,
    datetime_utc: datetimeUtc,
  };
}

export async function getObservation(location: ObservationLocation, datetimeUtc: string): Promise<Observation> {
  const value: unknown = await request("/api/astronomy/v1/observation", {
    method: "POST",
    body: JSON.stringify(observationRequest(location, datetimeUtc)),
  });
  return parseObservation(value);
}

export async function compareObservations(locations: ObservationLocation[], datetimeUtc: string): Promise<Observation[]> {
  const value: unknown = await request("/api/astronomy/v1/observations/batch", {
    method: "POST",
    body: JSON.stringify({ observations: locations.map((location) => observationRequest(location, datetimeUtc)) }),
  });
  if (!Array.isArray(value)) throw new ApiError("The astronomy comparison response was not a list.");
  return value.map(parseObservation);
}

export async function analyzeTerrain(siteId: number, startUtc: string, point: { lat: number; lon: number }): Promise<TerrainAnalysis> {
  const end = new Date(Date.parse(startUtc) + 24 * 60 * 60 * 1000).toISOString();
  const value: unknown = await request(`/api/analysis/sites/${siteId}/analyze`, {
    method: "POST",
    body: JSON.stringify({
      allow_synthetic: false,
      include_maps: true,
      point,
      config: {
        auto_select_point: true,
        sim: { start_utc: startUtc, end_utc: end, step_minutes: 60 },
        uncertainty: { runs: 0 },
      },
      ephemeris: { source: "horizons" },
    }),
  });
  if (!isRecord(value) || !isRecord(value.dataset) || !isRecord(value.assessment)) {
    throw new ApiError("The terrain response did not match the expected API shape.");
  }
  if (value.dataset.real_data !== true) throw new ApiError("The backend did not return a real LOLA terrain dataset; no synthetic result is shown.");
  return value as unknown as TerrainAnalysis;
}

export type TerrainPreview = { blob: Blob; source: string; product: string; resolutionM: number; coordinates: string; displayNote: string };

export async function getLolaTerrainPreview(lat: number, lon: number, radiusKm = 3): Promise<TerrainPreview> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/analysis/lola/preview?latitude_deg=${encodeURIComponent(lat)}&longitude_deg_east=${encodeURIComponent(lon)}&radius_km=${encodeURIComponent(radiusKm)}`, {
      headers: { Accept: "image/png" },
    });
  } catch {
    throw new ApiError("The backend could not be reached. Check that the API server is running.");
  }
  if (!response.ok) {
    let message = `LOLA terrain image request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
    } catch { /* Keep the status message for non-JSON errors. */ }
    throw new ApiError(message, response.status);
  }
  return {
    blob: await response.blob(),
    source: response.headers.get("X-Terrain-Source") ?? "NASA PGDA / LRO LOLA",
    product: response.headers.get("X-Terrain-Product") ?? "LOLA hillshade",
    resolutionM: Number(response.headers.get("X-Terrain-Resolution-M")) || 20,
    coordinates: response.headers.get("X-Terrain-Coordinates") ?? `${lat}, ${lon}`,
    displayNote: response.headers.get("X-Terrain-Display") ?? "Contrast adjusted for display",
  };
}
