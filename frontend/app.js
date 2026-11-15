const $ = (i) => document.getElementById(i),
  D = Math.PI / 180,
  RM = 1737.4,
  esc = (s) =>
    String(s).replace(
      /[&<>"]/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
    );
const SITES = [
  [
    "Shackleton Crater rim",
    "landing",
    -89.9,
    0,
    1.5,
    8,
    80,
    55,
    70,
    "modeled",
    55,
    95,
    "Rim ridges get near-continuous sunlight; the interior is a cold-trap PSR.",
  ],
  [
    "Connecting Ridge",
    "landing",
    -89.4,
    -137.5,
    1.8,
    6,
    90,
    50,
    60,
    "modeled",
    45,
    85,
    "Ridge linking Shackleton and de Gerlache; a leading candidate area.",
  ],
  [
    "Haworth Crater rim",
    "landing",
    -87.5,
    -5,
    0.5,
    9,
    60,
    50,
    70,
    "modeled",
    70,
    85,
    "Large PSR crater with rugged rim terrain.",
  ],
  [
    "Faustini Crater rim",
    "landing",
    -87.3,
    77,
    0.3,
    7,
    55,
    45,
    65,
    "modeled",
    65,
    80,
    "Deep PSR crater with possible volatiles.",
  ],
  [
    "de Gerlache Crater rim",
    "landing",
    -88.5,
    -87,
    0.8,
    8,
    65,
    40,
    60,
    "modeled",
    60,
    80,
    "Crater with PSR floor near the pole.",
  ],
  [
    "Malapert Massif",
    "landing",
    -86,
    0,
    5,
    5,
    75,
    95,
    40,
    "hypothetical",
    40,
    70,
    "Massif with a near-constant line of sight to Earth.",
  ],
  [
    "Cabeus Crater",
    "psr",
    -84.9,
    -35.5,
    -1,
    10,
    10,
    35,
    85,
    "observed",
    65,
    100,
    "LCROSS detected water-bearing material in the ejecta (NASA source listed in Sources & attribution).",
  ],
  [
    "Nobile Crater rim",
    "landing",
    -85.3,
    53,
    0.6,
    7,
    60,
    40,
    55,
    "hypothetical",
    50,
    75,
    "Candidate region near the pole.",
  ],
  [
    "Apollo 11 (Tranquility Base)",
    "landmark",
    0.67,
    23.47,
    -2,
    3,
    50,
    95,
    0,
    "observed",
    20,
    80,
    "First crewed landing, July 1969.",
  ],
  [
    "Apollo 17 (Taurus–Littrow)",
    "landmark",
    20.19,
    30.77,
    -2.5,
    6,
    50,
    90,
    0,
    "observed",
    35,
    75,
    "Last Apollo mission, December 1972.",
  ],
  [
    "Tycho Crater",
    "landmark",
    -43.3,
    -11.4,
    0,
    15,
    50,
    90,
    0,
    "hypothetical",
    75,
    70,
    "Young, bright-rayed impact crater.",
  ],
  [
    "Copernicus Crater",
    "landmark",
    9.7,
    -20.1,
    0,
    14,
    50,
    90,
    0,
    "hypothetical",
    60,
    70,
    "Large crater with terraced walls and central peaks.",
  ],
  [
    "Aristarchus Plateau",
    "landmark",
    23.7,
    -47.4,
    0,
    8,
    50,
    85,
    0,
    "hypothetical",
    55,
    80,
    "Volcanic plateau with very bright terrain.",
  ],
].map((a, i) => ({
  id: i,
  n: a[0],
  k: a[1],
  lat: a[2],
  lon: a[3],
  el: a[4],
  sl: a[5],
  sun: a[6],
  com: a[7],
  ice: a[8],
  ip: a[9],
  haz: a[10],
  sci: a[11],
  note: a[12],
}));
const W = { sl: 5, sun: 5, com: 4, ice: 4, haz: 5, sci: 3 },
  WL = {
    sl: "Gentle slope",
    sun: "Sunlight",
    com: "Earth visibility",
    ice: "Water-ice potential",
    haz: "Low hazard",
    sci: "Science value",
  };
let S = { sel: null, favs: [], cmp: [], mode: false, tour: -1 },
  P = { start: null, wps: [], speed: 1, hrs: 8, margin: 20, stop: 4 },
  SAVED = [],
  view = "dash";
try {
  const j = JSON.parse(localStorage.getItem("lmn") || "{}");
  S.favs = j.favs || [];
  SAVED = j.plans || [];
} catch (e) {}
const persist = () => {
  try {
    localStorage.setItem("lmn", JSON.stringify({ favs: S.favs, plans: SAVED }));
  } catch (e) {}
};
const score = (s) => {
  const c = {
    sl: Math.max(0, 100 - s.sl * 8),
    sun: s.sun,
    com: s.com,
    ice: s.ice,
    haz: 100 - s.haz,
    sci: s.sci,
  };
  let t = 0,
    w = 0;
  for (const k in W) {
    t += c[k] * W[k];
    w += W[k];
  }
  return { c, v: w ? Math.round(t / w) : 0 };
};
const risk = (s) =>
  s.haz >= 65 || s.sl >= 10 ? "High" : s.haz >= 45 ? "Moderate" : "Low";
const fmt = (la, lo) =>
  `${Math.abs(la).toFixed(2)}°${la < 0 ? "S" : "N"}, ${Math.abs(lo).toFixed(2)}°${lo < 0 ? "W" : "E"}`;
const bar = (v, c = "var(--cy)") =>
  `<div class="bar"><i style="width:${Math.max(0, Math.min(100, v))}%;background:${c}"></i></div>`;
const badge = (p) => `<span class="bd ${p}">${p}</span>`;
const ll = (la, lo, r = 1) => {
  const p = (lo + 180) * D,
    t = (90 - la) * D;
  return new THREE.Vector3(
    -r * Math.cos(p) * Math.sin(t),
    r * Math.cos(t),
    r * Math.sin(p) * Math.sin(t),
  );
};
const v2ll = (v) => {
  v = v.clone().normalize();
  let lo = Math.atan2(v.z, -v.x) / D - 180;
  if (lo < -180) lo += 360;
  return [Math.asin(v.y) / D, lo];
};
const dist = (a, b) =>
  RM *
  Math.acos(Math.max(-1, Math.min(1, ll(a.lat, a.lon).dot(ll(b.lat, b.lon)))));
const ang = (a, b, c, d) =>
  Math.acos(Math.max(-1, Math.min(1, ll(a, b).dot(ll(c, d))))) / D;
// ---------- 3D ----------
let ren,
  sc,
  cam,
  G,
  moon,
  gSites,
  gPsr,
  gGrid,
  gRoute,
  cursor,
  rover,
  tgtQ = null,
  tgtZ = null,
  path = [],
  rv = -1;
function tex() {
  const c = document.createElement("canvas");
  c.width = 1024;
  c.height = 512;
  const x = c.getContext("2d"),
    X = (l) => ((l + 180) / 360) * 1024,
    Y = (l) => ((90 - l) / 180) * 512;
  x.fillStyle = "#8c8c8c";
  x.fillRect(0, 0, 1024, 512);
  let r = 7;
  const q = () => (r = (r * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 900; i++) {
    const g = x.createRadialGradient(q() * 1024, q() * 512, 0, 0, 0, 1);
    x.fillStyle = `rgba(${q() > 0.5 ? 255 : 60},${q() > 0.5 ? 255 : 60},${q() > 0.5 ? 255 : 60},.05)`;
    x.beginPath();
    x.arc(q() * 1024, q() * 512, 6 + q() * 30, 0, 7);
    x.fill();
  }
  [
    [32, -16, 18],
    [28, 18, 9],
    [8, 31, 10],
    [17, 59, 6],
    [-21, -16, 8],
    [18, -57, 20],
    [-4, 52, 8],
    [-24, -39, 6],
  ].forEach((m) => {
    x.fillStyle = "rgba(40,42,52,.55)";
    x.beginPath();
    x.ellipse(
      X(m[1]),
      Y(m[0]),
      (m[2] / 360) * 1024,
      (m[2] / 180) * 512 * 1.1,
      0,
      0,
      7,
    );
    x.fill();
  });
  for (let i = 0; i < 900; i++) {
    const px = q() * 1024,
      py = q() * 512,
      s = 1 + q() * q() * 9;
    x.strokeStyle = "rgba(235,235,235,.35)";
    x.fillStyle = "rgba(50,50,50,.25)";
    x.beginPath();
    x.arc(px, py, s, 0, 7);
    x.fill();
    x.stroke();
  }
  return new THREE.CanvasTexture(c);
}
function init() {
  try {
    ren = new THREE.WebGLRenderer({ canvas: $("cv"), antialias: true });
  } catch (e) {
    $("stage").insertAdjacentHTML(
      "beforeend",
      '<div class="ov" style="top:50%;left:20%">3D is unavailable in this browser (WebGL error). The panels still work.</div>',
    );
    return false;
  }
  sc = new THREE.Scene();
  cam = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  cam.position.z = 3.6;
  G = new THREE.Group();
  sc.add(G);
  moon = new THREE.Mesh(
    new THREE.SphereGeometry(1, 64, 48),
    new THREE.MeshLambertMaterial({ map: tex() }),
  );
  G.add(moon);
  if (THREE.GLTFLoader) {
    const modelUrl = location.pathname.startsWith("/standalone-demo/")
      ? "../frontend/assets/moon.glb"
      : "assets/moon.glb";
    new THREE.GLTFLoader().load(
      modelUrl,
      (gltf) => {
        const model = gltf.scene;
        model.updateMatrixWorld(true);
        const bounds = new THREE.Box3().setFromObject(model),
          center = bounds.getCenter(new THREE.Vector3()),
          size = bounds.getSize(new THREE.Vector3()),
          scale = 2 / Math.max(size.x, size.y, size.z);
        model.scale.setScalar(scale);
        model.position.set(
          -center.x * scale,
          -center.y * scale,
          -center.z * scale,
        );
        G.remove(moon);
        moon = model;
        G.add(moon);
        const badge = document.getElementById("moon-model-status");
        if (badge) badge.textContent = "NASA LRO 3D model loaded";
      },
      undefined,
      (e) => {
        console.warn(
          "NASA Moon model could not be loaded; using the illustrative fallback.",
          e,
        );
        const badge = document.getElementById("moon-model-status");
        if (badge)
          badge.textContent = "NASA model unavailable · illustrative fallback";
      },
    );
  }
  sc.add(new THREE.AmbientLight(0xffffff, 0.55));
  const dl = new THREE.DirectionalLight(0xffffff, 0.95);
  dl.position.set(-3, 1.5, 4);
  sc.add(dl);
  const sp = [];
  for (let i = 0; i < 900; i++) {
    const v = new THREE.Vector3(
      Math.random() - 0.5,
      Math.random() - 0.5,
      Math.random() - 0.5,
    )
      .normalize()
      .multiplyScalar(40);
    sp.push(v.x, v.y, v.z);
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute("position", new THREE.Float32BufferAttribute(sp, 3));
  sc.add(
    new THREE.Points(
      sg,
      new THREE.PointsMaterial({ size: 0.12, color: 0xffffff }),
    ),
  );
  gSites = new THREE.Group();
  gPsr = new THREE.Group();
  gGrid = new THREE.Group();
  gRoute = new THREE.Group();
  gGrid.visible = false;
  G.add(gSites, gPsr, gGrid, gRoute);
  const up = new THREE.Vector3(0, 0, 1);
  SITES.forEach((s) => {
    const m = new THREE.Mesh(
      new THREE.SphereGeometry(0.02, 12, 8),
      new THREE.MeshBasicMaterial({
        color: s.k == "landing" ? 0xff9a3c : s.k == "psr" ? 0x31d4ff : 0xffffff,
      }),
    );
    m.position.copy(ll(s.lat, s.lon, 1.012));
    gSites.add(m);
    if (/Shackleton|Haworth|Faustini|Gerlache|Cabeus/.test(s.n)) {
      const d = new THREE.Mesh(
        new THREE.CircleGeometry(0.05, 24),
        new THREE.MeshBasicMaterial({
          color: 0x31d4ff,
          transparent: true,
          opacity: 0.35,
          side: THREE.DoubleSide,
        }),
      );
      d.position.copy(ll(s.lat, s.lon, 1.003));
      d.quaternion.setFromUnitVectors(up, d.position.clone().normalize());
      gPsr.add(d);
    }
  });
  const pts = [];
  for (let la = -60; la <= 60; la += 30)
    for (let lo = -180; lo < 180; lo += 5)
      pts.push(ll(la, lo, 1.002), ll(la, lo + 5, 1.002));
  for (let lo = -180; lo < 180; lo += 30)
    for (let la = -85; la < 85; la += 5)
      pts.push(ll(la, lo, 1.002), ll(la + 5, lo, 1.002));
  gGrid.add(
    new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({
        color: 0x31d4ff,
        transparent: true,
        opacity: 0.35,
      }),
    ),
  );
  cursor = new THREE.Mesh(
    new THREE.RingGeometry(0.035, 0.05, 28),
    new THREE.MeshBasicMaterial({ color: 0x31d4ff, side: THREE.DoubleSide }),
  );
  cursor.visible = false;
  G.add(cursor);
  rover = new THREE.Mesh(
    new THREE.SphereGeometry(0.018, 10, 8),
    new THREE.MeshBasicMaterial({ color: 0x5be3a0 }),
  );
  rover.visible = false;
  G.add(rover);
  focus(0, 0, 3.6);
  G.quaternion.copy(tgtQ);
  tgtQ = null;
  const cv = $("cv"),
    Pm = new Map();
  let md = 0,
    pd = 0;
  cv.onpointerdown = (e) => {
    cv.setPointerCapture(e.pointerId);
    Pm.set(e.pointerId, [e.clientX, e.clientY]);
    md = 0;
    tgtQ = null;
  };
  cv.onpointermove = (e) => {
    const p = Pm.get(e.pointerId);
    if (!p) return;
    if (Pm.size == 2) {
      const o = [...Pm.entries()].find((a) => a[0] != e.pointerId)[1],
        d = Math.hypot(e.clientX - o[0], e.clientY - o[1]);
      if (pd)
        cam.position.z = Math.max(
          1.5,
          Math.min(6, cam.position.z + (pd - d) * 0.01),
        );
      pd = d;
    } else {
      const dx = e.clientX - p[0],
        dy = e.clientY - p[1],
        k = (0.0045 * cam.position.z) / 3.6;
      md += Math.abs(dx) + Math.abs(dy);
      G.quaternion.premultiply(
        new THREE.Quaternion().setFromEuler(new THREE.Euler(dy * k, dx * k, 0)),
      );
    }
    p[0] = e.clientX;
    p[1] = e.clientY;
  };
  cv.onpointerup = (e) => {
    Pm.delete(e.pointerId);
    pd = 0;
    if (md < 6 && !Pm.size) pick(e);
  };
  cv.onpointercancel = (e) => Pm.delete(e.pointerId);
  cv.onwheel = (e) => {
    e.preventDefault();
    cam.position.z = Math.max(
      1.5,
      Math.min(6, cam.position.z + e.deltaY * 0.002),
    );
  };
  const loop = () => {
    const w = $("stage").clientWidth,
      h = $("stage").clientHeight;
    if (cv.width != w * devicePixelRatio) {
      ren.setPixelRatio(devicePixelRatio);
      ren.setSize(w, h, false);
      cam.aspect = w / h;
      cam.updateProjectionMatrix();
    }
    if (tgtQ) {
      G.quaternion.slerp(tgtQ, 0.09);
      if (G.quaternion.angleTo(tgtQ) < 0.002) tgtQ = null;
    }
    if (tgtZ) {
      cam.position.z += (tgtZ - cam.position.z) * 0.09;
      if (Math.abs(tgtZ - cam.position.z) < 0.01) tgtZ = null;
    }
    if (rv >= 0 && path.length > 1) {
      rv += 0.004;
      if (rv >= 1) {
        rv = -1;
        rover.visible = false;
      } else {
        const f = rv * (path.length - 1),
          i = Math.floor(f);
        rover.position.lerpVectors(
          path[i],
          path[Math.min(i + 1, path.length - 1)],
          f - i,
        );
      }
    }
    ren.render(sc, cam);
    requestAnimationFrame(loop);
  };
  loop();
  return true;
}
function focus(la, lo, z) {
  tgtQ = new THREE.Quaternion().setFromUnitVectors(
    ll(la, lo),
    new THREE.Vector3(0, 0, 1),
  );
  if (z) tgtZ = z;
}
function pick(e) {
  const r = $("cv").getBoundingClientRect(),
    rc = new THREE.Raycaster();
  rc.setFromCamera(
    new THREE.Vector2(
      ((e.clientX - r.left) / r.width) * 2 - 1,
      (-(e.clientY - r.top) / r.height) * 2 + 1,
    ),
    cam,
  );
  const h = rc.intersectObject(moon, true)[0];
  if (!h) return;
  const [la, lo] = v2ll(G.worldToLocal(h.point.clone()));
  let b = null,
    bd = (3.2 * cam.position.z) / 3.6;
  SITES.forEach((s) => {
    const d = ang(la, lo, s.lat, s.lon);
    if (d < bd) {
      bd = d;
      b = s;
    }
  });
  if (S.mode)
    addWp(
      b
        ? { lat: b.lat, lon: b.lon, n: b.n }
        : { lat: la, lon: lo, n: "Waypoint" },
    );
  else b ? select(b.id) : select({ lat: la, lon: lo });
}
// ---------- state / render ----------
function select(x, fly) {
  S.sel = x;
  const p = typeof x == "number" ? SITES[x] : x;
  if (cursor) {
    cursor.visible = true;
    cursor.position.copy(ll(p.lat, p.lon, 1.015));
    cursor.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 0, 1),
      cursor.position.clone().normalize(),
    );
  }
  if (fly && G) focus(p.lat, p.lon, 2.6);
  renderAll();
}
function addWp(w) {
  P.wps.push(w);
  renderAll();
}
function rInfo() {
  const x = S.sel,
    el = $("info");
  if (x == null) {
    el.innerHTML =
      "<h3>No location selected</h3><p class='mu'>Click the Moon, search, or pick a site to open its intelligence card.</p>";
    return;
  }
  if (typeof x == "object") {
    el.innerHTML = `<h3>Custom location</h3><p>${fmt(x.lat, x.lon)}</p><p class="mu">No sample data for this point. Terrain, sunlight and ice values are not available here.</p><div class="row"><button data-a="wpc">Add as waypoint</button></div>`;
    return;
  }
  const s = SITES[x],
    sc2 = score(s),
    r = risk(s),
    pros = Object.keys(W)
      .filter((k) => sc2.c[k] >= 70)
      .map((k) => WL[k]),
    cons = Object.keys(W)
      .filter((k) => sc2.c[k] <= 40)
      .map((k) => WL[k]);
  const t =
    s.sun < 20
      ? "≈ −170 °C or colder (permanently shadowed, modeled)"
      : s.lat < -80
        ? "≈ −190 to −50 °C over a lunar day (modeled, typical)"
        : "≈ −170 to +120 °C over a lunar day (typical)";
  el.innerHTML = `<h3>${S.favs.includes(x) ? "★ " : ""}${s.n}</h3><p class="mu">${fmt(s.lat, s.lon)} · ${s.k}</p><p>${s.note}</p>
<table><tr><td>Elevation (sample)</td><td>≈ ${s.el} km</td></tr><tr><td>Slope (sample)</td><td>≈ ${s.sl}°</td></tr><tr><td>Sunlight exposure</td><td>${s.sun}% ${badge("modeled")}</td></tr><tr><td>Temperature</td><td>${t}</td></tr><tr><td>Water-ice potential</td><td>${s.ice}/100 ${badge(s.ip)}</td></tr></table>
<h3 style="margin-top:8px">Suitability ${sc2.v}/100 · Risk: <span style="color:${r == "High" ? "var(--bad)" : r == "Low" ? "var(--ok)" : "var(--or)"}">${r}</span></h3>${bar(sc2.v, "var(--or)")}
<p><b>Pros:</b> ${pros.join(", ") || "none strong"}<br><b>Cons:</b> ${cons.join(", ") || "none major"}</p>
<p class="mu">Why: weighted blend of slope, sunlight, comms, ice, hazard and science value. Simulated; not an official NASA recommendation.</p>
<div class="row"><button data-a="fav">${S.favs.includes(x) ? "Unfavorite" : "★ Favorite"}</button><button data-a="land" class="pri">Set as landing site</button><button data-a="wps">Add waypoint</button><button data-a="cmp" data-i="${x}">Compare</button></div>`;
}
function rDash() {
  const ranked = SITES.slice()
      .sort((a, b) => score(b).v - score(a).v)
      .slice(0, 3),
    L = pl();
  $("dash").innerHTML =
    `<h3>Mission status</h3><table><tr><td>Landing site</td><td>${P.start != null ? SITES[P.start].n : "not set"}</td></tr><tr><td>Waypoints</td><td>${P.wps.length}</td></tr><tr><td>Route / duration</td><td>${L.km.toFixed(1)} km · ${L.days.toFixed(1)} days</td></tr><tr><td>Site data</td><td>${LIVE ? "PostGIS database via API (sample values)" : "Sample data (offline)"} ${badge("modeled")}</td></tr></table>
<h3 style="margin-top:8px">Top simulated sites</h3>${ranked.map((s) => `<button data-a="sel" data-i="${s.id}" style="display:block;width:100%;text-align:left;margin-bottom:4px">${s.n} — ${score(s).v}</button>`).join("")}
<h3 style="margin-top:8px">Guided tour</h3><div id="tour"></div>`;
  rTour();
}
const TOUR = [
  [
    8,
    "Start with Apollo 11: humanity’s first landing was at a low-latitude, smooth, well-lit mare.",
  ],
  [
    5,
    "Malapert Massif: a tall peak near the pole that keeps Earth in view for direct communication.",
  ],
  [
    0,
    "Shackleton’s rim: sunlight for power, next to a shadowed crater that may trap ice.",
  ],
  [
    6,
    "Cabeus: LCROSS detected water-bearing material in impact ejecta in 2009.",
  ],
  [
    1,
    "Connecting Ridge: a ridge with high sunlight that links two polar craters.",
  ],
];
function rTour() {
  const t = $("tour");
  if (!t) return;
  t.innerHTML =
    S.tour < 0
      ? '<button data-a="tour" data-i="0" class="pri">Start tour</button>'
      : `<p>${S.tour + 1}/${TOUR.length}: ${TOUR[S.tour][1]}</p><div class="row"><button data-a="tour" data-i="${S.tour - 1}" ${S.tour ? "" : "disabled"}>Back</button><button data-a="tour" data-i="${S.tour + 1}">${S.tour == TOUR.length - 1 ? "Finish" : "Next"}</button></div>`;
}
function rExplore() {
  $("sitelist").innerHTML = SITES.map(
    (s) =>
      `<button data-a="sel" data-i="${s.id}">${S.favs.includes(s.id) ? "★ " : ""}${s.n}<br><span class="mu">${fmt(s.lat, s.lon)}</span></button>`,
  ).join("");
}
function rSouth() {
  $("south").innerHTML =
    SITES.filter((s) => s.lat < -80)
      .map(
        (s) =>
          `<div style="margin-top:8px"><b>${s.n}</b> ${badge(s.ip)}<br><span class="mu">Water-ice potential</span>${bar(s.ice, "var(--cy)")}<span class="mu">Sunlight</span>${bar(s.sun, "var(--or)")}<span class="mu">Terrain hazard</span>${bar(s.haz, "var(--bad)")}</div>`,
      )
      .join("") +
    '<p class="mu">Habitat candidates: high-sun, low-slope, low-hazard rims near ice (hypothetical).</p>';
}
function rWts() {
  $("wts").innerHTML = Object.keys(W)
    .map(
      (k) =>
        `<label>${WL[k]} <b id="wv-${k}">${W[k]}</b><input type="range" min="0" max="10" value="${W[k]}" data-w="${k}" style="width:100%"></label>`,
    )
    .join("");
}
function rRank() {
  const r = SITES.slice().sort((a, b) => score(b).v - score(a).v);
  $("rank").innerHTML =
    "<h3 style='margin-top:8px'>Ranking</h3>" +
    r
      .map(
        (s, i) =>
          `<div class="row" style="margin:2px 0"><input type="checkbox" data-a="cmp" data-i="${s.id}" ${S.cmp.includes(s.id) ? "checked" : ""} aria-label="Compare ${s.n}"><button data-a="sel" data-i="${s.id}" style="flex:1;text-align:left">${i + 1}. ${s.n} <b>${score(s).v}</b> · ${risk(s)}</button></div>`,
      )
      .join("");
  const c = S.cmp.map((i) => SITES[i]);
  $("cmp").innerHTML =
    c.length < 2
      ? '<p class="mu">Tick 2–3 sites to compare them.</p>'
      : `<table><tr><th></th>${c.map((s) => `<th>${s.n.split(" ")[0]}</th>`).join("")}</tr>${Object.keys(
          W,
        )
          .map(
            (k) =>
              `<tr><td>${WL[k]}</td>${c.map((s) => `<td>${Math.round(score(s).c[k])}</td>`).join("")}</tr>`,
          )
          .join(
            "",
          )}<tr><td><b>Score</b></td>${c.map((s) => `<td><b>${score(s).v}</b></td>`).join("")}</tr><tr><td>Risk</td>${c.map((s) => `<td>${risk(s)}</td>`).join("")}</tr></table>`;
}
function pl() {
  const pts = (P.start != null ? [SITES[P.start]] : []).concat(P.wps),
    legs = [];
  let km = 0;
  for (let i = 1; i < pts.length; i++) {
    const d = dist(pts[i - 1], pts[i]);
    legs.push([pts[i - 1].n, pts[i].n, d]);
    km += d;
  }
  const dh = (km / P.speed) * (1 + P.margin / 100),
    tot = dh + P.wps.length * P.stop;
  return { pts, legs, km, dh, tot, days: tot / P.hrs };
}
function rPlan() {
  const L = pl();
  $("plan").innerHTML =
    P.start == null
      ? '<p class="mu">No landing site yet. Select a site and press “Set as landing site”.</p>'
      : `<table><tr><td>Start</td><td>${esc(SITES[P.start].n)}</td></tr>${L.legs.map((l, i) => `<tr><td>${esc(l[1])}</td><td>${l[2].toFixed(1)} km <button data-a="rm" data-i="${i}" aria-label="Remove waypoint">✕</button></td></tr>`).join("")}</table>${L.legs.length ? "" : '<p class="mu">Add waypoints to build a route.</p>'}<p><b>${L.km.toFixed(1)} km</b> · driving ${L.dh.toFixed(0)} h · total ${L.tot.toFixed(0)} h · <b>≈ ${L.days.toFixed(1)} days</b> at ${P.hrs} h/day</p>`;
  drawRoute(L);
  $("pmode").textContent = "Click-to-add: " + (S.mode ? "ON" : "off");
  $("saved").innerHTML = SAVED.length
    ? SAVED.map(
        (p, i) =>
          `<div class="row"><span style="flex:1">${esc(p.name)} <span class="mu">${p.km.toFixed(0)} km</span></span><button data-a="load" data-i="${i}">Load</button><button data-a="del" data-i="${i}">Delete</button></div>`,
      ).join("")
    : '<p class="mu">No saved plans yet.</p>';
}
function drawRoute(L) {
  if (!gRoute) return;
  while (gRoute.children.length) gRoute.remove(gRoute.children[0]);
  path = [];
  const pts = L.pts;
  pts.forEach((p, i) => {
    const m = new THREE.Mesh(
      new THREE.SphereGeometry(0.016, 10, 8),
      new THREE.MeshBasicMaterial({ color: i ? 0x31d4ff : 0x5be3a0 }),
    );
    m.position.copy(ll(p.lat, p.lon, 1.01));
    gRoute.add(m);
  });
  for (let i = 1; i < pts.length; i++) {
    const a = ll(pts[i - 1].lat, pts[i - 1].lon),
      b = ll(pts[i].lat, pts[i].lon),
      an = Math.acos(Math.max(-1, Math.min(1, a.dot(b)))),
      n = Math.max(2, Math.ceil((an / D) * 2));
    for (let k = 0; k <= n; k++) {
      const t = k / n,
        v =
          an < 1e-6
            ? a.clone()
            : a
                .clone()
                .multiplyScalar(Math.sin((1 - t) * an))
                .add(b.clone().multiplyScalar(Math.sin(t * an)))
                .multiplyScalar(1 / Math.sin(an));
      path.push(v.multiplyScalar(1.008));
    }
  }
  if (path.length > 1)
    gRoute.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(path),
        new THREE.LineBasicMaterial({ color: 0xff9a3c }),
      ),
    );
}
const DS = [
  [
    "NASA PGDA / LRO LOLA",
    "Terrain analysis can load locally downloaded 5 m/pixel south-pole elevation products.",
    "https://pgda.gsfc.nasa.gov/products/78",
    "Download required",
  ],
  [
    "JPL Horizons",
    "Live Sun and Earth ephemerides for terrain analysis when Horizons is selected.",
    "https://ssd.jpl.nasa.gov/horizons/",
    "Live integration",
  ],
  [
    "NASA Image and Video Library",
    "The connection button checks a live image search; these results do not feed the site scores.",
    "https://images.nasa.gov/",
    "Live search check",
  ],
  [
    "NASA Goddard Moon model",
    "Bundled LRO imagery and topography model used by the 3D globe.",
    "https://svs.gsfc.nasa.gov/14959/",
    "Bundled asset",
  ],
  [
    "LROC QuickMap (ASU)",
    "External tool for exploring high-resolution lunar imagery and topography.",
    "https://quickmap.lroc.asu.edu/",
    "Reference only",
  ],
  [
    "NASA Moon Trek",
    "External lunar mapping and visualization tool; not queried by this ZIP build.",
    "https://trek.nasa.gov/moon/",
    "Reference only",
  ],
  [
    "CSA Moon Exploration",
    "Canadian Space Agency mission and program information.",
    "https://www.asc-csa.gc.ca/eng/astronomy/moon-exploration/",
    "Reference only",
  ],
  [
    "LRO Diviner",
    "Thermal data source; this application does not ingest Diviner data.",
    "https://diviner.ucla.edu/",
    "Not connected",
  ],
];
function rData() {
  $("ds").innerHTML =
    `<table><tr><th>Source</th><th>How this project uses it</th><th>Status</th></tr>${DS.map(([name, use, url, status]) => `<tr><td><a href="${url}" target="_blank" rel="noopener">${name}</a></td><td>${use}</td><td>${status}</td></tr>`).join("")}</table><p class="mu">Landing-site scores and ice, sunlight, and hazard values remain illustrative samples. Real LOLA-based terrain results are available only after the corresponding files are downloaded. The NASA image search button checks connectivity only.</p>`;
}
function report() {
  const L = pl();
  return (
    `LUNAR MOON NAVIGATOR: MISSION REPORT (simulated, educational)\nLanding site: ${P.start != null ? SITES[P.start].n : "not set"}\n` +
    L.legs
      .map((l, i) => `Leg ${i + 1}: ${l[0]} -> ${l[1]}: ${l[2].toFixed(1)} km`)
      .join("\n") +
    `\nTotal distance: ${L.km.toFixed(1)} km\nAssumptions: ${P.speed} km/h, ${P.hrs} operating h/day, ${P.margin}% margin, ${P.stop} h per stop\nEstimated duration: ${L.days.toFixed(1)} days (${L.tot.toFixed(0)} h)\nData: illustrative sample values, not NASA data; not an official recommendation.`
  );
}
function renderAll() {
  rInfo();
  rDash();
  rExplore();
  rSouth();
  rRank();
  rPlan();
  $("status").textContent = S.mode
    ? "Click-to-add is ON: click the Moon to add route waypoints."
    : S.sel == null
      ? "Select a location to begin."
      : "Selected: " +
        (typeof S.sel == "number" ? SITES[S.sel].n : fmt(S.sel.lat, S.sel.lon));
}
let LIVE = false,
  TOKEN = null,
  USER = null;
try {
  TOKEN = localStorage.getItem("lmn_tok");
} catch (e) {}
const api = async (p, o = {}) => {
  const h = { "Content-Type": "application/json" };
  if (TOKEN) h.Authorization = "Bearer " + TOKEN;
  const r = await fetch("/api" + p, Object.assign({ headers: h }, o));
  if (!r.ok) {
    let d = "Request failed";
    try {
      d = (await r.json()).detail || d;
    } catch (e) {}
    throw new Error(
      typeof d == "string"
        ? d
        : "Invalid input (email format, password 8+ characters)",
    );
  }
  return r.status == 204 ? null : r.json();
};
function rAcct() {
  const a = $("acct");
  if (!LIVE) {
    a.hidden = true;
    return;
  }
  a.hidden = false;
  a.innerHTML = USER
    ? `<b>Signed in:</b> ${esc(USER.email)} <button data-a="logout">Sign out</button><p class="mu">Favorites and plans sync to the database.</p>`
    : `<b>Account</b><div class="row"><input id="ac-email" type="email" placeholder="Email" aria-label="Email" autocomplete="username"><input id="ac-pw" type="password" placeholder="Password (8+)" aria-label="Password" autocomplete="current-password"></div><div class="row"><button data-a="login">Sign in</button><button data-a="register">Register</button></div><p class="mu">Optional: sign in to sync favorites and plans.</p>`;
}
async function authDo(kind) {
  try {
    const t = await api("/auth/" + kind, {
      method: "POST",
      body: JSON.stringify({
        email: $("ac-email").value,
        password: $("ac-pw").value,
      }),
    });
    TOKEN = t.token;
    try {
      localStorage.setItem("lmn_tok", TOKEN);
    } catch (e) {}
    await afterAuth();
  } catch (e) {
    $("status").textContent = e.message;
  }
}
async function afterAuth() {
  try {
    USER = await api("/me");
    const f = await api("/favorites");
    S.favs = f
      .map((id) => SITES.findIndex((s) => s.db == id))
      .filter((i) => i >= 0);
    const p = await api("/plans");
    SAVED = p.map((x) => ({
      name: x.name,
      dbid: x.id,
      km: x.distance_km || 0,
      P: x.params,
    }));
  } catch (e) {
    TOKEN = null;
    USER = null;
    try {
      localStorage.removeItem("lmn_tok");
    } catch (x) {}
  }
  rAcct();
  renderAll();
}
async function boot() {
  try {
    const r = await fetch("/api/sites");
    if (!r.ok) throw 0;
    const j = await r.json();
    if (!Array.isArray(j) || !j.length) throw 0;
    SITES.length = 0;
    j.forEach((a, i) =>
      SITES.push({
        id: i,
        db: a.id,
        n: a.name,
        k: a.kind,
        lat: a.lat,
        lon: a.lon,
        el: a.elevation_km,
        sl: a.slope_deg,
        sun: a.sunlight_pct,
        com: a.comms_pct,
        ice: a.ice_score,
        ip: a.ice_provenance,
        haz: a.hazard,
        sci: a.science,
        note: a.note || "",
      }),
    );
    LIVE = true;
  } catch (e) {
    LIVE = false;
  }
  mkDl();
  init();
  rWts();
  rData();
  setView("dash");
  renderAll();
  rAcct();
  if (LIVE && TOKEN) await afterAuth();
}

// ---------- terrain & mission analysis (Member 2 engine) ----------
let TDS = null;
async function terrainInit() {
  const n = $("t-note");
  if (!LIVE) {
    n.innerHTML =
      '<div class="alert">Terrain analysis needs the backend. Run <code>docker compose up</code> and open this page from http://localhost:8000.</div>';
    return;
  }
  n.textContent =
    "Computes slope, hazards, terrain-blocked sunlight and Earth line-of-sight from NASA LOLA elevation data.";
  if ($("t-start").value === "")
    $("t-start").value = new Date().toISOString().slice(0, 10);
  if (!TDS) {
    try {
      TDS = await api("/analysis/datasets");
    } catch (e) {
      n.innerHTML = '<div class="alert">' + esc(e.message) + "</div>";
      return;
    }
  }
  $("t-site").innerHTML = TDS.sites
    .map(
      (s) =>
        `<option value="${s.site_id}">${esc(s.site_name)} · ${s.elevation_present ? "real NASA DEM ✓" : "no DEM yet (synthetic demo)"}</option>`,
    )
    .join("");
}
const stc = (s) => `<span class="st-${s}">${s}</span>`;
function terrainCfg() {
  const st = Date.parse($("t-start").value + "T00:00:00Z") || Date.now(),
    d = +$("t-days").value || 30;
  return {
    auto_select_point: $("t-auto").checked,
    lander: {
      footprint_radius_m: +$("t-rad").value,
      max_slope_deg: +$("t-slope").value,
      max_relief_m: +$("t-relief").value,
    },
    sim: {
      start_utc: new Date(st).toISOString(),
      end_utc: new Date(st + d * 864e5).toISOString(),
      step_minutes: +$("t-step").value || 30,
    },
    uncertainty: { runs: +$("t-mc").value },
  };
}
async function terrainRun() {
  const o = $("t-out"),
    id = $("t-site").value;
  if (!id) {
    o.innerHTML = '<div class="alert">Backend not connected.</div>';
    return;
  }
  o.innerHTML =
    '<p class="mu">Running… live JPL Horizons queries can take up to a minute.</p>';
  try {
    const r = await api("/analysis/sites/" + id + "/analyze", {
      method: "POST",
      body: JSON.stringify({
        config: terrainCfg(),
        ephemeris: { source: $("t-eph").value },
        include_maps: true,
        allow_synthetic: true,
      }),
    });
    renderTerrain(r);
  } catch (e) {
    o.innerHTML = '<div class="alert">' + esc(e.message) + "</div>";
  }
}
async function terrainRank() {
  const o = $("t-out");
  if (!TDS || !TDS.sites.length) return;
  o.innerHTML =
    '<p class="mu">Ranking up to 6 sites… this can take a few minutes.</p>';
  try {
    const r = await api("/analysis/compare", {
      method: "POST",
      body: JSON.stringify({
        site_ids: TDS.sites.slice(0, 6).map((s) => s.site_id),
        config: terrainCfg(),
        ephemeris: { source: $("t-eph").value },
        allow_synthetic: true,
      }),
    });
    o.innerHTML = `<h3>Ranking</h3><div class="tbl"><table><tr><th>#</th><th>Site</th><th>Status</th><th>Score</th><th>Sun %</th><th>Earth %</th><th>Data</th></tr>${r.ranking.map((x) => `<tr><td>${x.rank}</td><td>${esc(x.site)}</td><td>${stc(x.status)}</td><td>${x.score ?? "–"}</td><td>${x.illumination_percent == null ? "–" : x.illumination_percent.toFixed(1)}</td><td>${x.earth_visibility_percent == null ? "–" : x.earth_visibility_percent.toFixed(1)}</td><td>${x.real_data ? "NASA" : "synthetic"}</td></tr>`).join("")}</table></div><p class="mu">${esc(r.note)} Terrain differs per site, so each uses its own analysis point.</p>`;
  } catch (e) {
    o.innerHTML = '<div class="alert">' + esc(e.message) + "</div>";
  }
}
const ramp = (t) =>
  `hsl(${240 - 240 * Math.min(1, Math.max(0, t))},75%,${28 + 22 * Math.min(1, t)}%)`;
function drawTerrainMap(m) {
  const c = $("t-map");
  if (!c) return;
  const k = m.slope_deg[0].length,
    n = m.slope_deg.length,
    w = Math.min(300, c.parentElement.clientWidth - 4),
    cs = w / k;
  c.width = w;
  c.height = cs * n;
  const x = c.getContext("2d");
  for (let i = 0; i < n; i++)
    for (let j = 0; j < k; j++) {
      const v = m.slope_deg[i][j];
      x.fillStyle = v == null ? "#333" : ramp(v / 30);
      x.fillRect(j * cs, i * cs, cs + 0.5, cs + 0.5);
      const h = m.hazard_class[i][j];
      if (h >= 2) {
        x.fillStyle = h == 2 ? "rgba(255,80,100,.45)" : "rgba(160,160,160,.5)";
        x.fillRect(j * cs, i * cs, cs + 0.5, cs + 0.5);
      }
    }
  x.strokeStyle = "#31d4ff";
  x.lineWidth = 2;
  x.beginPath();
  x.arc(
    m.point_rc[1] * cs + cs / 2,
    m.point_rc[0] * cs + cs / 2,
    Math.max(4, m.footprint_radius_px * cs),
    0,
    7,
  );
  x.stroke();
}
function drawHorizon(h) {
  const c = $("t-hz");
  if (!c) return;
  const w = c.clientWidth || 320,
    ht = 150;
  c.width = w;
  c.height = ht;
  const x = c.getContext("2d"),
    top = Math.max(
      8,
      Math.ceil(Math.max(...h.sun_horizon_deg, ...h.antenna_horizon_deg)) + 3,
    ),
    bot = -3,
    X = (a) => (a / 360) * w,
    Y = (e) => ht - 16 - ((e - bot) / (top - bot)) * (ht - 24);
  x.fillStyle = "#0c1230";
  x.fillRect(0, 0, w, ht);
  x.strokeStyle = "rgba(120,180,255,.25)";
  x.fillStyle = "#a3b3d8";
  x.font = "10px system-ui";
  [0, 5, 10]
    .filter((e) => e < top)
    .forEach((e) => {
      x.beginPath();
      x.moveTo(0, Y(e));
      x.lineTo(w, Y(e));
      x.stroke();
      x.fillText(e + "°", 2, Y(e) - 2);
    });
  x.fillStyle = "#3a4a78";
  x.beginPath();
  x.moveTo(0, ht);
  h.sun_horizon_deg.forEach((e, a) => x.lineTo(X(a), Y(e)));
  x.lineTo(w, ht);
  x.fill();
  x.strokeStyle = "#5bb8ff";
  x.beginPath();
  h.antenna_horizon_deg.forEach((e, a) =>
    a ? x.lineTo(X(a), Y(e)) : x.moveTo(X(a), Y(e)),
  );
  x.stroke();
  x.fillStyle = "#a3b3d8";
  [
    ["N", 0],
    ["E", 90],
    ["S", 180],
    ["W", 270],
  ].forEach(([t, a]) => x.fillText(t, Math.max(2, X(a) - 3), ht - 3));
}
function drawTimeline(r) {
  const c = $("t-tl");
  if (!c || !r.illumination) return;
  const w = c.clientWidth || 320,
    ht = 64;
  c.width = w;
  c.height = ht;
  const x = c.getContext("2d"),
    a = Date.parse(r.provenance.simulation_interval.start_utc),
    b = Date.parse(r.provenance.simulation_interval.end_utc),
    X = (t) => ((Date.parse(t) - a) / (b - a)) * w;
  x.fillStyle = "#0c1230";
  x.fillRect(0, 0, w, ht);
  [
    [r.illumination.sunlight_intervals, "#ffb347", 4],
    [r.communication.visibility_windows, "#5bb8ff", 36],
  ].forEach(([iv, col, y]) => {
    x.fillStyle = "rgba(255,255,255,.08)";
    x.fillRect(0, y, w, 22);
    x.fillStyle = col;
    iv.forEach((i) =>
      x.fillRect(
        X(i.start_utc),
        y,
        Math.max(1, X(i.end_utc) - X(i.start_utc)),
        22,
      ),
    );
  });
}
function renderTerrain(r) {
  const a = r.assessment,
    t = r.terrain,
    hz = r.hazards,
    il = r.illumination,
    cm = r.communication,
    u = r.uncertainty,
    d = r.dataset,
    p = r.analysis_point,
    f = (x) => (x == null ? "–" : (+x).toFixed(1));
  const ban = d.real_data
    ? `<div class="okb">Real NASA LOLA terrain: ${esc(d.source || "")} · ${esc(String(d.resolution_m))} m/px · ${esc(d.coordinate_frame || "")}</div>`
    : `<div class="alert"><b>SYNTHETIC terrain, not lunar data.</b> Download the NASA products (scripts/download_data.py) for real results.</div>`;
  $("t-out").innerHTML =
    ban +
    `<h3>${esc(r.site_name)} · <span class="st-${a.status}">${esc(a.status.replace(/_/g, " "))}</span></h3><p class="mu">Score ${a.score ?? "–"}/100${a.score_complete ? "" : " (partial: missing " + esc(a.missing_components.join(", ")) + ")"} · criteria: ${esc(a.criteria_source)} · weights: demo settings</p><p class="mu">${esc(a.interpretation)}</p>
<p>Point ${p.lat_deg.toFixed(4)}°, ${p.lon_deg_east.toFixed(3)}°E · ${esc(p.selection.replace(/_/g, " "))} · elevation ${f(p.ground_elevation_m)} m</p>
<h3>Landing footprint checks: ${stc(hz.footprint_status)}</h3><div class="tbl"><table><tr><th>Check</th><th>Status</th><th>Value</th><th>Limit</th></tr>${hz.checks.map((c) => `<tr title="${esc(c.detail)}"><td>${esc(c.name.replace(/_/g, " "))}</td><td>${stc(c.status)}</td><td>${f(c.value)} ${esc(c.units)}</td><td>${c.limit == null ? "–" : f(c.limit)}</td></tr>`).join("")}</table></div>
<h3>Terrain map</h3><canvas id="t-map" class="cv2"></canvas><p class="mu">Slope (blue 0° → red 30°); red tint = footprint would FAIL, grey = UNKNOWN; circle = analysed footprint. ${hz.craters_detected} crater candidate(s).</p>
<table><tr><td>Mean / p95 / max slope (window)</td><td>${f(t.mean_slope_deg)} / ${f(t.p95_slope_deg)} / ${f(t.max_slope_deg)}°</td></tr><tr><td>Median roughness</td><td>${(t.roughness_m || 0).toFixed(2)} m</td></tr><tr><td>Elevation range</td><td>${f(t.elevation_range_m[0])} to ${f(t.elevation_range_m[1])} m</td></tr></table>` +
    (il
      ? `<h3>Sunlight (terrain-aware)</h3><table><tr><td>Illuminated</td><td>${f(il.percent_illuminated)}% (${f(il.sunlight_hours)} h)</td></tr><tr><td>Longest sunlight / darkness</td><td>${f(il.longest_sunlight_hours)} h / ${f(il.longest_darkness_hours)} h</td></tr><tr><td>Hours blocked by terrain</td><td>${f(il.terrain_blocked_hours)} h</td></tr><tr><td>Sunrise/sunset events</td><td>${il.transitions.length}</td></tr></table>
<h3>Earth line of sight (geometric)</h3><table><tr><td>Visible</td><td>${f(cm.visibility_percent)}% (${f(cm.visibility_hours)} h)</td></tr><tr><td>Longest window / blackout</td><td>${f(cm.longest_window_hours)} h / ${f(cm.longest_blackout_hours)} h</td></tr><tr><td>Terrain obstruction</td><td>${esc(cm.terrain_obstruction_status)}</td></tr></table>
<canvas id="t-tl" class="cv2"></canvas><p class="mu"><span style="color:var(--or)">■</span> Sun above terrain · <span style="color:var(--cy)">■</span> Earth visible · grey = gap. Not a radio link budget.</p>`
      : '<p class="mu">Sun/Earth not computed (source = none).</p>') +
    `<h3>Horizon mask</h3><canvas id="t-hz" class="cv2"></canvas><p class="mu">Terrain skyline from the point (blue line: antenna height). ${(100 * r.horizon.edge_limited_fraction).toFixed(0)}% of directions are limited by the tile edge.</p>` +
    (u
      ? `<h3>Uncertainty (Monte Carlo)</h3><p>${u.pass_count}/${u.simulation_runs} realizations meet all criteria → confidence indicator <b>${f(u.confidence_indicator_percent)}%</b>. <span class="mu">${esc(u.interpretation)}</span></p>`
      : "") +
    `<details class="t"><summary>Data quality &amp; provenance</summary><p class="mu">Valid ${(100 * d.quality_window.valid_fraction).toFixed(1)}% · interpolated ${d.quality_window.interpolated_fraction == null ? "n/a" : (100 * d.quality_window.interpolated_fraction).toFixed(0) + "%"} · confidence ${f(d.quality_window.confidence_score)} · ${esc(r.provenance.algorithm_version)}${r.provenance.sky ? " · sky: " + esc(r.provenance.sky.source || "") : ""}${r.run_id ? " · run #" + r.run_id : ""}</p></details>
<details class="t"><summary>Limitations &amp; warnings (${r.limitations.length + r.warnings.length})</summary><ul>${r.limitations
      .concat(r.warnings)
      .map((x) => "<li class='mu'>" + esc(x) + "</li>")
      .join("")}</ul></details>`;
  if (r.maps) drawTerrainMap(r.maps);
  drawHorizon(r.horizon);
  drawTimeline(r);
}
// ---------- events ----------
const NAV = [
  ["dash", "Mission Dashboard"],
  ["explore", "3D Moon Explorer"],
  ["south", "Lunar South Pole"],
  ["analysis", "Landing Site Analysis"],
  ["terrain", "Terrain Analysis"],
  ["astronomy", "Astronomy"],
  ["plan", "Mission Planner"],
  ["data", "Scientific Data"],
  ["about", "About the Project"],
];
NAV.forEach((n) =>
  $("nav").insertAdjacentHTML(
    "beforeend",
    `<button data-a="nav" data-i="${n[0]}">${n[1]}</button>`,
  ),
);
function setView(v) {
  view = v;
  document
    .querySelectorAll(".v")
    .forEach((e) => e.classList.toggle("on", e.id == "v-" + v));
  document
    .querySelectorAll("#nav button")
    .forEach((b) => b.setAttribute("aria-current", b.dataset.i == v));
  if (v == "south" && G) {
    focus(-90, 0, 2.4);
  }
  if (v == "terrain") terrainInit();
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-a]");
  if (!b || (b.tagName == "INPUT" && b.type != "checkbox")) return;
  const a = b.dataset.a,
    i = b.dataset.i;
  if (a == "nav") setView(i);
  else if (a == "sel") select(+i, true);
  else if (a == "fav") {
    const k = S.favs.indexOf(S.sel);
    k < 0 ? S.favs.push(S.sel) : S.favs.splice(k, 1);
    persist();
    renderAll();
    if (USER)
      api("/favorites/" + SITES[S.sel].db, {
        method: k < 0 ? "PUT" : "DELETE",
      }).catch((e) => ($("status").textContent = e.message));
  } else if (a == "land") {
    P.start = S.sel;
    P.wps = [];
    renderAll();
  } else if (a == "wps") {
    const s = SITES[S.sel];
    addWp({ lat: s.lat, lon: s.lon, n: s.n });
  } else if (a == "wpc")
    addWp({ lat: S.sel.lat, lon: S.sel.lon, n: "Waypoint" });
  else if (a == "cmp") {
    const k = S.cmp.indexOf(+i);
    if (k >= 0) S.cmp.splice(k, 1);
    else {
      if (S.cmp.length >= 3) S.cmp.shift();
      S.cmp.push(+i);
    }
    renderAll();
  } else if (a == "pole" && G) focus(-90, 0, 2.4);
  else if (a == "pmode") {
    S.mode = !S.mode;
    renderAll();
  } else if (a == "clr") {
    P.wps = [];
    renderAll();
  } else if (a == "rm") {
    P.wps.splice(+i, 1);
    renderAll();
  } else if (a == "rover") {
    if (path.length > 1 && rover) {
      rover.visible = true;
      rv = 0;
    } else
      $("status").textContent =
        "Build a route first (landing site plus at least one waypoint).";
  } else if (a == "save") {
    const L = pl();
    if (P.start == null || !L.legs.length) {
      $("status").textContent =
        "Add a landing site and at least one waypoint before saving.";
      return;
    }
    SAVED.push({
      name: $("pl-name").value || "Plan " + (SAVED.length + 1),
      P: JSON.parse(JSON.stringify(P)),
      km: L.km,
    });
    persist();
    renderAll();
    if (USER) {
      const en = SAVED[SAVED.length - 1];
      api("/plans", {
        method: "POST",
        body: JSON.stringify({
          name: en.name,
          start_site_id: SITES[P.start].db,
          waypoints: P.wps.map((w) => ({
            lat: w.lat,
            lon: w.lon,
            name: String(w.n || "Waypoint").slice(0, 80),
          })),
          params: en.P,
          distance_km: L.km,
          duration_days: L.days,
        }),
      })
        .then((r) => {
          en.dbid = r.id;
        })
        .catch((x) => ($("status").textContent = x.message));
    }
  } else if (a == "load") {
    P = Object.assign({}, SAVED[+i].P);
    ["speed", "hrs", "margin", "stop"].forEach(
      (k) => ($("pl-" + k).value = P[k]),
    );
    renderAll();
  } else if (a == "del") {
    const d = SAVED.splice(+i, 1)[0];
    persist();
    renderAll();
    if (USER && d.dbid)
      api("/plans/" + d.dbid, { method: "DELETE" }).catch(() => {});
  } else if (a == "report") {
    $("rep").hidden = false;
    $("cp").hidden = false;
    $("rep").value = report();
  } else if (a == "copy") {
    try {
      navigator.clipboard.writeText($("rep").value).then(
        () => ($("status").textContent = "Report copied."),
        () => {
          $("rep").select();
          $("status").textContent = "Select and copy the text manually.";
        },
      );
    } catch (x) {
      $("rep").select();
    }
  } else if (a == "tour") {
    S.tour = +i >= TOUR.length ? -1 : +i;
    if (S.tour >= 0) select(TOUR[S.tour][0], true);
    else rTour();
  } else if (a == "tan") terrainRun();
  else if (a == "trank") terrainRank();
  else if (a == "login" || a == "register") authDo(a);
  else if (a == "logout") {
    TOKEN = null;
    USER = null;
    try {
      localStorage.removeItem("lmn_tok");
    } catch (e) {}
    rAcct();
  } else if (a == "api") {
    $("apistat").textContent = "Contacting NASA…";
    const c = new AbortController(),
      t = setTimeout(() => c.abort(), 5000);
    fetch(
      LIVE
        ? "/api/nasa/search?q=lunar%20south%20pole"
        : "https://images-api.nasa.gov/search?q=lunar%20south%20pole&media_type=image",
      { signal: c.signal },
    )
      .then((r) => {
        if (!r.ok) throw 0;
        return r.json();
      })
      .then((j) => {
        const it = j.items || j.collection.items;
        $("apistat").textContent =
          "Live: " +
          it.length +
          " results" +
          (j.items
            ? " (" +
              j.items
                .slice(0, 3)
                .map((x) => x.title)
                .join("; ") +
              ")"
            : "") +
          (j.items ? " via backend proxy" : " direct") +
          ".";
      })
      .catch(
        () =>
          ($("apistat").textContent =
            "NASA API unreachable from this page (network policy or offline). Using clearly labeled sample data."),
      )
      .finally(() => clearTimeout(t));
  }
});
$("wts").addEventListener("input", (e) => {
  const k = e.target.dataset.w;
  if (k) {
    W[k] = +e.target.value;
    $("wv-" + k).textContent = W[k];
    rRank();
    rDash();
    rInfo();
  }
});
["speed", "hrs", "margin", "stop"].forEach(
  (k) =>
    ($("pl-" + k).oninput = (e) => {
      P[k] = Math.max(k == "speed" ? 0.1 : 0, +e.target.value || 0) || P[k];
      rPlan();
      rDash();
    }),
);
const mkDl = () => {
  $("dl").innerHTML = SITES.map((s) => `<option value="${s.n}">`).join("");
};
$("q").onkeydown = (e) => {
  if (e.key != "Enter") return;
  const v = e.target.value.trim(),
    m = v.match(/^(-?\d+(?:\.\d+)?)\s*[,; ]\s*(-?\d+(?:\.\d+)?)$/);
  if (m) {
    const la = +m[1],
      lo = +m[2];
    if (Math.abs(la) <= 90 && Math.abs(lo) <= 180) {
      select({ lat: la, lon: lo }, true);
      return;
    }
  }
  const s = SITES.find((s) => s.n.toLowerCase().includes(v.toLowerCase()));
  s && v
    ? select(s.id, true)
    : ($("status").textContent =
        "No match for “" + v + "”. Try a site name or “lat, lon”.");
};
[
  ["Lsites", () => gSites],
  ["Lpsr", () => gPsr],
  ["Lgrid", () => gGrid],
  ["Lroute", () => gRoute],
].forEach(
  ([id, g]) =>
    ($(id).onchange = (e) => {
      if (g()) g().visible = e.target.checked;
    }),
);
boot();
