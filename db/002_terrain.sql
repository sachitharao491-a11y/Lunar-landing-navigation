-- Terrain-analysis migration (idempotent). Safe to run on an existing database.
ALTER TABLE data_sources DROP CONSTRAINT IF EXISTS data_sources_status_check;
ALTER TABLE data_sources ADD CONSTRAINT data_sources_status_check CHECK (status IN (
  'live-proxy','live-integration','download-required','bundled-asset',
  'reference-only','not-connected','sample'
));

INSERT INTO data_sources (name,description,url,status) VALUES
  ('NASA Image and Video Library','Public image search proxied by the backend; the UI button checks connectivity only','https://images-api.nasa.gov','live-proxy'),
  ('JPL Horizons','Live Sun/Earth observer ephemerides used by terrain analysis when selected','https://ssd.jpl.nasa.gov/horizons/','live-integration'),
  ('NASA PGDA / LRO LOLA','Terrain analysis can read local 5 m DEM files downloaded on demand','https://pgda.gsfc.nasa.gov/products/78','download-required'),
  ('NASA Goddard SVS Moon model','Bundled LRO imagery/topography asset used by the globe','https://svs.gsfc.nasa.gov/14959/','bundled-asset'),
  ('LROC QuickMap (ASU)','External lunar mapping reference; not queried by the app','https://quickmap.lroc.asu.edu/','reference-only'),
  ('NASA Moon Trek','External lunar mapping reference; not queried by this build','https://trek.nasa.gov/moon/','reference-only'),
  ('CSA Moon Exploration','External mission and program reference','https://www.asc-csa.gc.ca/eng/astronomy/moon-exploration/','reference-only'),
  ('LRO / Diviner','Radiometer source; this app does not ingest Diviner products','https://diviner.ucla.edu/','not-connected'),
  ('NASA PDS Geosciences Node','Archive reference; this build downloads LOLA products from PGDA','https://pds-geosciences.wustl.edu/','not-connected'),
  ('Site attributes in this database','Hand-entered illustrative values, not NASA measurements','','sample')
ON CONFLICT (name) DO UPDATE SET description=EXCLUDED.description, url=EXCLUDED.url, status=EXCLUDED.status;

ALTER TABLE sites ADD COLUMN IF NOT EXISTS pgda_key TEXT;   -- NASA PGDA LOLA site key (see backend/app/terrain/ingestion/registry.py)

UPDATE sites SET pgda_key = v.k FROM (VALUES
  ('Shackleton Crater rim','Site04'), ('Connecting Ridge','Site01'), ('Haworth Crater rim','Haworth'),
  ('Faustini Crater rim','LM7'), ('de Gerlache Crater rim','Site11'), ('Malapert Massif','Site23'),
  ('Cabeus Crater','NPA'), ('Nobile Crater rim','Site06')) AS v(n, k)
WHERE sites.name = v.n AND sites.pgda_key IS NULL;

-- Registry of loaded terrain products (provenance: file hash, version, resolution, frame).
CREATE TABLE IF NOT EXISTS terrain_datasets (
  id            SERIAL PRIMARY KEY,
  site_id       INT REFERENCES sites(id) ON DELETE CASCADE,
  pgda_key      TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('elevation','count','slope','z_uncertainty','slope_uncertainty','illumination_ref')),
  source        TEXT NOT NULL,
  source_url    TEXT,
  file_path     TEXT NOT NULL,
  sha256        TEXT,
  resolution_m  REAL,
  crs           TEXT,
  loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (pgda_key, role)
);

-- Every analysis run is stored with its full configuration and result for traceability.
CREATE TABLE IF NOT EXISTS analysis_runs (
  id                SERIAL PRIMARY KEY,
  site_id           INT REFERENCES sites(id) ON DELETE SET NULL,
  user_id           INT REFERENCES users(id) ON DELETE SET NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  algorithm_version TEXT NOT NULL,
  dataset_real      BOOLEAN NOT NULL,
  ephemeris_source  TEXT,
  status            TEXT,               -- assessment.status
  score             REAL,
  config            JSONB NOT NULL,
  result            JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS analysis_runs_site_idx ON analysis_runs (site_id, created_at DESC);

-- The application connects with the private database role; deny direct access through Supabase Data API roles.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE mission_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE terrain_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs ENABLE ROW LEVEL SECURITY;
