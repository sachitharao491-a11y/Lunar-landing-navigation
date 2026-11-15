import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { Observation, Site } from "./types/api";

const api = vi.hoisted(() => ({
  getSites: vi.fn(), getDataSources: vi.fn(), getTerrainCatalog: vi.fn(),
  getObservation: vi.fn(), compareObservations: vi.fn(), analyzeTerrain: vi.fn(),
  getLolaTerrainPreview: vi.fn(),
}));
vi.mock("./services/api", () => api);
vi.mock("./components/MoonScene", () => ({ MoonScene: () => <div aria-label="visual-only Moon model" /> }));

const sites: Site[] = [
  { id: 4, name: "Shackleton Rim", kind: "landing", lat: -89.68, lon: 129, elevation_km: 1.5, slope_deg: 8, sunlight_pct: 80, comms_pct: 55, ice_score: 70, ice_provenance: "modeled", hazard: 55, science: 95, note: null, source: "Illustrative sample record", source_date: null, confidence: "low" },
  { id: 5, name: "Connecting Ridge", kind: "landing", lat: -89.45, lon: -136, elevation_km: 1.8, slope_deg: 6, sunlight_pct: 90, comms_pct: 50, ice_score: 60, ice_provenance: "modeled", hazard: 45, science: 85, note: null, source: "Illustrative sample record", source_date: null, confidence: "low" },
];

const observation: Observation = {
  site: { name: sites[0].name, latitude_deg: sites[0].lat, longitude_deg_east: sites[0].lon, altitude_km: 0 },
  datetime_utc: "2026-11-15T06:00:00+00:00",
  sun: { target_body: "Sun", target_id: "10", site: { name: sites[0].name, latitude_deg: sites[0].lat, longitude_deg_east: sites[0].lon, altitude_km: 0 }, datetime_utc: "2026-11-15T06:00:00+00:00", azimuth_deg: 123.45, elevation_deg: 42.25, ra_deg: null, dec_deg: null, range_km: 149000000, range_rate_km_s: null, illuminated_fraction: null, phase_angle_deg: null, is_above_horizon: true },
  earth: { target_body: "Earth", target_id: "399", site: { name: sites[0].name, latitude_deg: sites[0].lat, longitude_deg_east: sites[0].lon, altitude_km: 0 }, datetime_utc: "2026-11-15T06:00:00+00:00", azimuth_deg: 234.5, elevation_deg: 4.2, ra_deg: null, dec_deg: null, range_km: 375000, range_rate_km_s: null, illuminated_fraction: null, phase_angle_deg: null, is_above_horizon: true },
  earth_visibility: { earth_center_above_geometric_horizon: true, geometric_line_of_sight: true, earth_elevation_deg: 4.2, radio_link_assessment: "not_assessed", radio_link_note: "A radio link budget was not calculated." },
  solar_irradiance: { sun_center_above_geometric_horizon: true, sun_distance_km: 149000000, direct_normal_w_m2: 1361, horizontal_surface_w_m2: 924, reference_tsi_w_m2: 1361, reference_source: "NASA GSFC nominal TSI", reference_source_url: "https://example.test", method: "Backend nominal estimate", limitations: "Simplified; terrain and slope not modeled." },
  data_source: "JPL Horizons API", position_type: "airless apparent observer quantities", visibility_scope: "geometric; terrain obstruction not included",
};

beforeEach(() => {
  api.getSites.mockResolvedValue(sites);
  api.getDataSources.mockResolvedValue([]);
  api.getTerrainCatalog.mockResolvedValue({ source: "PGDA", lroc_reference: "", data_dir: "", fallback: "", sites: sites.map((site) => ({ site_id: site.id, site_name: site.name, pgda_key: "site", pgda_name: "LOLA", elevation_present: false, products_present: {}, urls: {} })) });
  api.getObservation.mockResolvedValue(observation);
  api.compareObservations.mockResolvedValue([]);
  api.analyzeTerrain.mockReset();
});

describe("mission interface", () => {
  it("shows Horizons values returned by the API without recalculating them", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Shackleton Rim" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Observation latitude")).toHaveValue(-89.68));
    fireEvent.click(screen.getByRole("button", { name: /request observation/i }));
    expect(await screen.findByText(/42\.25/)).toBeInTheDocument();
    expect(screen.getByText(/234\.50/)).toBeInTheDocument();
    expect(screen.getByText(/radio link: not_assessed/i)).toBeInTheDocument();
  });

  it("sends user-entered coordinates for a single observation", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "Shackleton Rim" });
    await waitFor(() => expect(screen.getByLabelText("Observation latitude")).toHaveValue(-89.68));
    fireEvent.change(screen.getByLabelText("Observation latitude"), { target: { value: "-88.25" } });
    fireEvent.change(screen.getByLabelText("Observation east longitude"), { target: { value: "42.5" } });
    fireEvent.click(screen.getByRole("button", { name: /request observation/i }));
    expect(api.getObservation).toHaveBeenCalledWith({ site_name: "Custom lunar coordinates", latitude_deg: -88.25, longitude_deg_east: 42.5, altitude_km: 0 }, expect.any(String));
  });

  it("compares two independently selected custom coordinates at the same UTC time", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "Shackleton Rim" });
    fireEvent.change(screen.getByLabelText("Site A latitude"), { target: { value: "-88.1" } });
    fireEvent.change(screen.getByLabelText("Site A east longitude"), { target: { value: "16" } });
    fireEvent.change(screen.getByLabelText("Site B latitude"), { target: { value: "-83.75" } });
    fireEvent.change(screen.getByLabelText("Site B east longitude"), { target: { value: "-122" } });
    fireEvent.click(screen.getByRole("button", { name: /compare these sites/i }));
    expect(api.compareObservations).toHaveBeenCalledWith([
      { site_name: "Site A (custom)", latitude_deg: -88.1, longitude_deg_east: 16, altitude_km: 0 },
      { site_name: "Site B (custom)", latitude_deg: -83.75, longitude_deg_east: -122, altitude_km: 0 },
    ], expect.any(String));
  });

  it("shows unavailable terrain and does not request a synthetic substitute", async () => {
    render(<App />);
    expect(await screen.findByText(/No local 5 m LOLA raster is installed/)).toBeInTheDocument();
    expect(api.analyzeTerrain).not.toHaveBeenCalled();
  });

  it("shows a clear empty/error state when the backend catalog cannot load", async () => {
    api.getSites.mockRejectedValueOnce(new Error("The backend could not be reached."));
    render(<App />);
    expect(await screen.findByText("Site catalog unavailable")).toBeInTheDocument();
    expect(screen.getByText("The backend could not be reached.")).toBeInTheDocument();
  });
});
