-- Illustrative SAMPLE values (approximate, hand-entered). Not a NASA product; replace with LOLA/Diviner-derived values.
INSERT INTO sites (name,kind,geom,elevation_km,slope_deg,sunlight_pct,comms_pct,ice_score,ice_provenance,hazard,science,note,source,source_date,confidence) VALUES
('Shackleton Crater rim','landing',extensions.ST_SetSRID(extensions.ST_MakePoint(0,-89.9),100001),1.5,8,80,55,70,'modeled',55,95,'Rim ridges get near-continuous sunlight; the interior is a cold-trap PSR.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Connecting Ridge','landing',extensions.ST_SetSRID(extensions.ST_MakePoint(-137.5,-89.4),100001),1.8,6,90,50,60,'modeled',45,85,'Ridge linking Shackleton and de Gerlache; a leading candidate area.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Haworth Crater rim','landing',extensions.ST_SetSRID(extensions.ST_MakePoint(-5,-87.5),100001),0.5,9,60,50,70,'modeled',70,85,'Large PSR crater with rugged rim terrain.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Faustini Crater rim','landing',extensions.ST_SetSRID(extensions.ST_MakePoint(77,-87.3),100001),0.3,7,55,45,65,'modeled',65,80,'Deep PSR crater with possible volatiles.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('de Gerlache Crater rim','landing',extensions.ST_SetSRID(extensions.ST_MakePoint(-87,-88.5),100001),0.8,8,65,40,60,'modeled',60,80,'Crater with PSR floor near the pole.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Malapert Massif','landing',extensions.ST_SetSRID(extensions.ST_MakePoint(0,-86),100001),5,5,75,95,40,'hypothetical',40,70,'Massif with a near-constant line of sight to Earth.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Cabeus Crater','psr',extensions.ST_SetSRID(extensions.ST_MakePoint(-35.5,-84.9),100001),-1,10,10,35,85,'observed',65,100,'LCROSS detected water-bearing material in the impact ejecta (NASA mission source: https://science.nasa.gov/mission/lcross/).','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Nobile Crater rim','landing',extensions.ST_SetSRID(extensions.ST_MakePoint(53,-85.3),100001),0.6,7,60,40,55,'hypothetical',50,75,'Candidate region near the pole.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Apollo 11 (Tranquility Base)','landmark',extensions.ST_SetSRID(extensions.ST_MakePoint(23.47,0.67),100001),-2,3,50,95,0,'observed',20,80,'First crewed landing, July 1969.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Apollo 17 (Taurus-Littrow)','landmark',extensions.ST_SetSRID(extensions.ST_MakePoint(30.77,20.19),100001),-2.5,6,50,90,0,'observed',35,75,'Last Apollo mission, December 1972.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Tycho Crater','landmark',extensions.ST_SetSRID(extensions.ST_MakePoint(-11.4,-43.3),100001),0,15,50,90,0,'hypothetical',75,70,'Young, bright-rayed impact crater.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Copernicus Crater','landmark',extensions.ST_SetSRID(extensions.ST_MakePoint(-20.1,9.7),100001),0,14,50,90,0,'hypothetical',60,70,'Large crater with terraced walls and central peaks.','Illustrative sample (approximate; not live NASA data)',NULL,'low'),
('Aristarchus Plateau','landmark',extensions.ST_SetSRID(extensions.ST_MakePoint(-47.4,23.7),100001),0,8,50,85,0,'hypothetical',55,80,'Volcanic plateau with very bright terrain.','Illustrative sample (approximate; not live NASA data)',NULL,'low');
INSERT INTO data_sources (name,description,url,status) VALUES
('NASA Image and Video Library','Public NASA media search, proxied by this backend','https://images-api.nasa.gov','live-proxy'),
('JPL Horizons','Live observer ephemerides used by terrain analysis when selected','https://ssd.jpl.nasa.gov/horizons/','live-integration'),
('NASA PGDA / LRO LOLA','Terrain engine can read local 5 m DEM products downloaded on demand','https://pgda.gsfc.nasa.gov/products/78','download-required'),
('NASA Goddard SVS Moon model','Bundled LRO imagery and topography model used by the globe','https://svs.gsfc.nasa.gov/14959/','bundled-asset'),
('LROC QuickMap (ASU)','External lunar mapping reference; not queried by the app','https://quickmap.lroc.asu.edu/','reference-only'),
('NASA Moon Trek','External lunar mapping reference; not queried by this build','https://trek.nasa.gov/moon/','reference-only'),
('CSA Moon Exploration','External mission and program reference','https://www.asc-csa.gc.ca/eng/astronomy/moon-exploration/','reference-only'),
('LRO / Diviner','Radiometer source; this app does not ingest Diviner products','https://diviner.ucla.edu/','not-connected'),
('NASA PDS Geosciences Node','Archive reference; this build downloads LOLA products from PGDA','https://pds-geosciences.wustl.edu/','not-connected'),
('Site attributes in this database','Hand-entered illustrative values, not NASA measurements','','sample');
