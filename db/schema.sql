-- Lunar Moon Navigator schema for Supabase Postgres + PostGIS.
-- Enable PostGIS first in Supabase Dashboard > Database > Extensions (extensions schema).

-- Custom lunar coordinate system (Moon 2000 sphere, radius 1,737.4 km).
-- Using a Moon-specific SRID avoids mislabeling lunar points as Earth (EPSG:4326).
INSERT INTO extensions.spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text)
VALUES (100001, 'LUNAR', 1,
 'GEOGCS["Moon 2000",DATUM["D_Moon_2000",SPHEROID["Moon_2000",1737400,0]],PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]]',
 '+proj=longlat +a=1737400 +b=1737400 +no_defs')
ON CONFLICT (srid) DO NOTHING;

CREATE TABLE users (
  id            SERIAL PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sites (
  id             SERIAL PRIMARY KEY,
  name           TEXT UNIQUE NOT NULL,
  kind           TEXT NOT NULL CHECK (kind IN ('landing','psr','landmark')),
  geom           extensions.geometry(Point, 100001) NOT NULL,   -- lon (X), lat (Y), degrees
  elevation_km   REAL,
  slope_deg      REAL CHECK (slope_deg BETWEEN 0 AND 90),
  sunlight_pct   REAL CHECK (sunlight_pct BETWEEN 0 AND 100),
  comms_pct      REAL CHECK (comms_pct BETWEEN 0 AND 100),
  ice_score      REAL CHECK (ice_score BETWEEN 0 AND 100),
  ice_provenance TEXT NOT NULL CHECK (ice_provenance IN ('observed','modeled','hypothetical')),
  hazard         REAL CHECK (hazard BETWEEN 0 AND 100),
  science        REAL CHECK (science BETWEEN 0 AND 100),
  note           TEXT,
  source         TEXT NOT NULL,       -- where the numbers come from
  source_date    DATE,                -- dataset date, NULL when unknown
  confidence     TEXT NOT NULL DEFAULT 'low' CHECK (confidence IN ('low','medium','high'))
);
CREATE INDEX sites_geom_gix ON sites USING GIST (geom);
CREATE INDEX sites_kind_idx ON sites (kind);

CREATE TABLE data_sources (
  id          SERIAL PRIMARY KEY,
  name        TEXT UNIQUE NOT NULL,
  description TEXT,
  url         TEXT,
  status      TEXT NOT NULL CHECK (status IN (
    'live-proxy','live-integration','download-required','bundled-asset',
    'reference-only','not-connected','sample'
  ))
);

CREATE TABLE favorites (
  user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  site_id    INT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, site_id)
);

CREATE TABLE mission_plans (
  id            SERIAL PRIMARY KEY,
  user_id       INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  start_site_id INT REFERENCES sites(id) ON DELETE SET NULL,
  waypoints     JSONB NOT NULL DEFAULT '[]',
  params        JSONB NOT NULL DEFAULT '{}',   -- speed, operating hours, margin, stop time
  distance_km   REAL,
  duration_days REAL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX mission_plans_user_idx ON mission_plans (user_id);
