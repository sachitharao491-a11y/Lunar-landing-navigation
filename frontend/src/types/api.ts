export type Site = {
  id: number;
  name: string;
  kind: "landing" | "psr" | "landmark";
  lat: number;
  lon: number;
  elevation_km: number | null;
  slope_deg: number | null;
  sunlight_pct: number | null;
  comms_pct: number | null;
  ice_score: number | null;
  ice_provenance: "observed" | "modeled" | "hypothetical";
  hazard: number | null;
  science: number | null;
  note: string | null;
  source: string;
  source_date: string | null;
  confidence: "low" | "medium" | "high";
};

export type ObservationLocation = {
  site_name: string;
  latitude_deg: number;
  longitude_deg_east: number;
  altitude_km: number;
};

export type CelestialBody = {
  target_body: string;
  target_id: string;
  site: { name: string; latitude_deg: number; longitude_deg_east: number; altitude_km: number };
  datetime_utc: string;
  azimuth_deg: number | null;
  elevation_deg: number | null;
  ra_deg: number | null;
  dec_deg: number | null;
  range_km: number | null;
  range_rate_km_s: number | null;
  illuminated_fraction: number | null;
  phase_angle_deg: number | null;
  is_above_horizon: boolean | null;
};

export type Observation = {
  site: { name: string; latitude_deg: number; longitude_deg_east: number; altitude_km: number };
  datetime_utc: string;
  sun: CelestialBody;
  earth: CelestialBody;
  earth_visibility: {
    earth_center_above_geometric_horizon: boolean | null;
    geometric_line_of_sight: boolean | null;
    earth_elevation_deg: number | null;
    radio_link_assessment: string;
    radio_link_note: string;
  };
  solar_irradiance: {
    sun_center_above_geometric_horizon: boolean | null;
    sun_distance_km: number | null;
    direct_normal_w_m2: number | null;
    horizontal_surface_w_m2: number | null;
    reference_tsi_w_m2: number;
    reference_source: string;
    reference_source_url: string;
    method: string;
    limitations: string;
  };
  data_source: string;
  position_type: string;
  visibility_scope: string;
};

export type DataSource = { name: string; description: string | null; url: string | null; status: string };

export type TerrainCatalog = {
  source: string;
  lroc_reference: string;
  data_dir: string;
  fallback: string;
  sites: Array<{
    site_id: number;
    site_name: string;
    pgda_key: string;
    pgda_name: string;
    elevation_present: boolean;
    products_present: Record<string, boolean>;
    urls: Record<string, string>;
  }>;
};

export type TerrainAnalysis = {
  site_name: string;
  db_site_id: number;
  run_id: number | null;
  dataset: { real_data: boolean; source?: string; resolution_m?: number; coordinate_frame?: string };
  assessment: { status: string; score: number | null; score_complete: boolean; criteria_source: string; interpretation: string };
  illumination: { percent_illuminated: number | null; sunlight_hours?: number; terrain_blocked_hours?: number; sunlight_intervals?: Array<{ start_utc: string; end_utc: string }> } | null;
  communication: { visibility_percent: number | null; visibility_hours?: number; longest_window_hours?: number; terrain_obstruction_status?: string; visibility_windows?: Array<{ start_utc: string; end_utc: string }> } | null;
  maps?: {
    downsample_factor: number;
    pixel_m: number;
    extent_m: number[];
    point_rc: number[];
    footprint_radius_px: number;
    elevation_m: number[][];
    slope_deg: number[][];
    hazard_class: number[][];
    hazard_legend: Record<string, string>;
    note: string;
  };
  provenance: { algorithm_version: string; generated_at?: string; simulation_interval?: { start_utc: string; end_utc: string }; sky: { source?: string } | null };
  [key: string]: unknown;
};
