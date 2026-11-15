import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeTerrain, ApiError, compareObservations, getLolaTerrainPreview, getObservation, getSites } from "./api";
import type { Observation, ObservationLocation, Site } from "../types/api";

const site: Site = {
  id: 4, name: "Shackleton Rim", kind: "landing", lat: -89.68, lon: 129,
  elevation_km: 1.5, slope_deg: 8, sunlight_pct: 80, comms_pct: 55,
  ice_score: 70, ice_provenance: "modeled", hazard: 55, science: 95,
  note: null, source: "Illustrative sample", source_date: null, confidence: "low",
};

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

function observation(): Observation {
  const body = { target_body: "Sun", target_id: "10", site: { name: site.name, latitude_deg: site.lat, longitude_deg_east: site.lon, altitude_km: 0 }, datetime_utc: "2026-11-15T06:00:00Z", azimuth_deg: 123, elevation_deg: 12, ra_deg: null, dec_deg: null, range_km: 149000000, range_rate_km_s: null, illuminated_fraction: null, phase_angle_deg: null, is_above_horizon: true };
  return {
    site: body.site, datetime_utc: body.datetime_utc,
    sun: body, earth: { ...body, target_body: "Earth", target_id: "399", range_km: 375000 },
    earth_visibility: { earth_center_above_geometric_horizon: true, geometric_line_of_sight: true, earth_elevation_deg: 4, radio_link_assessment: "not_assessed", radio_link_note: "Not a link budget" },
    solar_irradiance: { sun_center_above_geometric_horizon: true, sun_distance_km: 149000000, direct_normal_w_m2: 1361, horizontal_surface_w_m2: 283, reference_tsi_w_m2: 1361, reference_source: "NASA GSFC nominal TSI", reference_source_url: "https://example.test", method: "Backend method", limitations: "Simplified estimate" },
    data_source: "JPL Horizons API", position_type: "airless apparent observer quantities", visibility_scope: "geometric; terrain obstruction not included",
  };
}

const location: ObservationLocation = { site_name: "Custom lunar coordinates", latitude_deg: -88.25, longitude_deg_east: 42.5, altitude_km: 0 };

afterEach(() => vi.unstubAllGlobals());

describe("frontend API service", () => {
  it("validates the backend site-list response", async () => {
    const fetchMock = vi.fn(async () => response([site]));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getSites()).resolves.toEqual([site]);
    vi.stubGlobal("fetch", vi.fn(async () => response([{ name: "missing required catalog fields" }])));
    await expect(getSites()).rejects.toThrow("site catalog response did not match");
  });

  it("sends entered coordinates to Horizons at the lunar reference surface", async () => {
    const fetchMock = vi.fn(async () => response(observation()));
    vi.stubGlobal("fetch", fetchMock);
    await getObservation(location, "2026-11-15T06:00:00Z");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/astronomy/v1/observation");
    expect(JSON.parse(String(init.body))).toMatchObject({
      site_name: location.site_name, latitude_deg: location.latitude_deg, longitude_deg_east: location.longitude_deg_east,
      altitude_km: 0, datetime_utc: "2026-11-15T06:00:00Z",
    });
  });

  it("rejects astronomy values whose API types are invalid", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ ...observation(), sun: { ...observation().sun, elevation_deg: "12" } })));
    await expect(getObservation(location, "2026-11-15T06:00:00Z")).rejects.toThrow("unexpected types");
  });

  it("sends two distinct sites together to the real batch endpoint", async () => {
    const fetchMock = vi.fn(async () => response([observation(), observation()]));
    vi.stubGlobal("fetch", fetchMock);
    await compareObservations([location, { ...location, site_name: "Site B", latitude_deg: -84.5, longitude_deg_east: -120 }], "2026-11-15T06:00:00Z");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/astronomy/v1/observations/batch");
    expect(JSON.parse(String(init.body)).observations).toMatchObject([
      { site_name: location.site_name, latitude_deg: -88.25, longitude_deg_east: 42.5 },
      { site_name: "Site B", latitude_deg: -84.5, longitude_deg_east: -120 },
    ]);
  });

  it("rejects malformed backend requests and results without real DEM data", async () => {
    const fetchMock = vi.fn(async () => response({ detail: "No real DEM" }, 404));
    vi.stubGlobal("fetch", fetchMock);
    await expect(analyzeTerrain(site.id, "2026-11-15T06:00:00Z", { lat: -88.25, lon: 42.5 })).rejects.toMatchObject({ status: 404 });
    const [, request] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(request.body))).toMatchObject({ allow_synthetic: false, include_maps: true, point: { lat: -88.25, lon: 42.5 } });
    vi.stubGlobal("fetch", vi.fn(async () => response({ dataset: { real_data: false }, assessment: {} })));
    await expect(analyzeTerrain(site.id, "2026-11-15T06:00:00Z", { lat: -88.25, lon: 42.5 })).rejects.toThrow("no synthetic result is shown");
  });

  it("loads binary NASA LOLA image responses with provenance headers", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, blob: async () => new Blob(["png"]), headers: new Headers({ "X-Terrain-Source": "NASA PGDA / LOLA", "X-Terrain-Resolution-M": "20", "X-Terrain-Coordinates": "-88.250000, 42.500000" }) } as Response));
    vi.stubGlobal("fetch", fetchMock);
    const result = await getLolaTerrainPreview(-88.25, 42.5);
    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toContain("latitude_deg=-88.25");
    expect(result).toMatchObject({ source: "NASA PGDA / LOLA", resolutionM: 20, coordinates: "-88.250000, 42.500000" });
    expect(result.blob).toBeInstanceOf(Blob);
  });

  it("turns network failures into a clear API error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    await expect(getSites()).rejects.toBeInstanceOf(ApiError);
    await expect(getSites()).rejects.toThrow("backend could not be reached");
  });
});
