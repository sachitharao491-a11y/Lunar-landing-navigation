"""Lunar Moon Navigator API (FastAPI + PostgreSQL/PostGIS)."""
import asyncio, datetime as dt, hashlib, hmac, json, logging, os, re, secrets, time
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg, httpx, jwt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .scoring import DEFAULT_WEIGHTS, route_stats, suitability

log = logging.getLogger("lunar")
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))
CORS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",") if o.strip()]
_FRONTEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
_BUILT_FRONTEND_DIR = os.path.join(_FRONTEND_ROOT, "dist")
_CONFIGURED_FRONTEND_DIR = os.getenv("FRONTEND_DIR")
# Prefer the compiled React app whenever it exists, including when a Docker .env
# still points at the legacy source directory. Before the first build, retain the
# static source tree as a useful fallback for backend-only development.
FRONTEND_DIR = _BUILT_FRONTEND_DIR if os.path.isdir(_BUILT_FRONTEND_DIR) else (
    _CONFIGURED_FRONTEND_DIR if _CONFIGURED_FRONTEND_DIR and os.path.isdir(_CONFIGURED_FRONTEND_DIR) else _FRONTEND_ROOT
)
if JWT_SECRET == "dev-only-change-me":
    log.warning("JWT_SECRET is the development default. Set a real secret in production.")

SITE_COLS = ("id,name,kind,ST_Y(geom) AS lat,ST_X(geom) AS lon,elevation_km,slope_deg,sunlight_pct,comms_pct,"
             "ice_score,ice_provenance,hazard,science,note,source,source_date,confidence")


async def _init(conn):
    # Supabase installs PostGIS in `extensions`; include it for geometry types and ST_* functions.
    await conn.execute("SET search_path TO public, extensions")
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


@asynccontextmanager
async def lifespan(app):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required. Set it to the Supabase session-pooler URL in .env.")
    for attempt in range(10):  # wait for the database on cold start
        try:
            app.state.pool = await asyncpg.create_pool(DATABASE_URL, init=_init, min_size=1, max_size=8)
            break
        except Exception as e:
            log.warning("DB not ready (%s), retry %d", e, attempt + 1)
            await asyncio.sleep(2)
    else:
        raise RuntimeError("Could not connect to the database")
    yield
    await app.state.pool.close()


app = FastAPI(title="Lunar Moon Navigator API", version="1.0.0", lifespan=lifespan,
              description="Educational lunar mission-planning API. Site values are illustrative samples.")
app.add_middleware(CORSMiddleware, allow_origins=CORS, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)

# --- Terrain & mission analysis engine (Member 2) and Member 1's astronomy service ---
from .api_terrain import router as terrain_router  # noqa: E402

app.include_router(terrain_router)
try:  # Member 1's FastAPI app, mounted unchanged (health, /v1/observation, /v1/observations/batch)
    from astronomy.web.app import app as astronomy_app  # noqa: E402

    app.mount("/api/astronomy", astronomy_app)
except Exception as _e:  # pragma: no cover
    log.warning("Member 1 astronomy app not mounted: %s", _e)


def pool(): return app.state.pool


# ---------- auth ----------
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return f"{salt}${hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 200_000).hex()}"


def check_pw(pw, stored):
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_pw(pw, salt), stored)


def make_token(uid):
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=JWT_MINUTES)
    return jwt.encode({"sub": str(uid), "exp": exp}, JWT_SECRET, algorithm="HS256")


async def current_user(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not cred:
        raise HTTPException(401, "Sign in required")
    try:
        uid = int(jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    row = await pool().fetchrow("SELECT id,email,display_name FROM users WHERE id=$1", uid)
    if not row:
        raise HTTPException(401, "Unknown user")
    return dict(row)


class Creds(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    password: str = Field(min_length=8, max_length=200)


@app.post("/api/auth/register", status_code=201)
async def register(c: Creds):
    try:
        uid = await pool().fetchval("INSERT INTO users(email,password_hash) VALUES($1,$2) RETURNING id",
                                    c.email.lower(), hash_pw(c.password))
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "Email already registered")
    return {"token": make_token(uid)}


@app.post("/api/auth/login")
async def login(c: Creds):
    row = await pool().fetchrow("SELECT id,password_hash FROM users WHERE email=$1", c.email.lower())
    if not row or not check_pw(c.password, row["password_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(row["id"])}


@app.get("/api/me")
async def me(u=Depends(current_user)): return u


# ---------- sites ----------
@app.get("/api/health")
async def health():
    await pool().fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/api/sites")
async def list_sites(kind: Optional[str] = Query(None, pattern="^(landing|psr|landmark)$"),
                     bbox: Optional[str] = Query(None, description="minLon,minLat,maxLon,maxLat")):
    where, args = [], []
    if kind:
        args.append(kind); where.append(f"kind=${len(args)}")
    if bbox:
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox.split(",")]
        except ValueError:
            raise HTTPException(422, "bbox must be four comma-separated numbers")
        args += [x1, y1, x2, y2]
        where.append(f"geom && ST_MakeEnvelope(${len(args)-3},${len(args)-2},${len(args)-1},${len(args)},100001)")
    sql = f"SELECT {SITE_COLS} FROM sites" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id"
    return [dict(r) for r in await pool().fetch(sql, *args)]


@app.get("/api/sites/{site_id}")
async def get_site(site_id: int):
    r = await pool().fetchrow(f"SELECT {SITE_COLS} FROM sites WHERE id=$1", site_id)
    if not r:
        raise HTTPException(404, "Site not found")
    s = dict(r)
    return {**s, "suitability": suitability(s)}


class ScoreReq(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)


@app.post("/api/score")
async def score_sites(req: ScoreReq):
    bad = [k for k in req.weights if k not in DEFAULT_WEIGHTS or not 0 <= req.weights[k] <= 10]
    if bad:
        raise HTTPException(422, f"Invalid weights: {bad}. Allowed keys {list(DEFAULT_WEIGHTS)} with values 0-10")
    rows = [dict(r) for r in await pool().fetch(f"SELECT {SITE_COLS} FROM sites")]
    ranked = sorted(({"id": s["id"], "name": s["name"], **suitability(s, req.weights)} for s in rows),
                    key=lambda x: -x["score"])
    return {"weights": {**DEFAULT_WEIGHTS, **req.weights}, "ranking": ranked}


# ---------- mission route ----------
class Waypoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    name: str = Field(default="Waypoint", max_length=80)


class RouteReq(BaseModel):
    start_site_id: int
    waypoints: list[Waypoint] = Field(max_length=50)
    speed_kmh: float = Field(default=1.0, gt=0, le=100)
    op_hours_per_day: float = Field(default=8, gt=0, le=24)
    margin_pct: float = Field(default=20, ge=0, le=300)
    stop_hours: float = Field(default=4, ge=0, le=240)


@app.post("/api/route")
async def route(req: RouteReq):
    r = await pool().fetchrow("SELECT name,ST_Y(geom) AS lat,ST_X(geom) AS lon FROM sites WHERE id=$1", req.start_site_id)
    if not r:
        raise HTTPException(404, "Start site not found")
    pts = [dict(r)] + [w.model_dump() for w in req.waypoints]
    return {**route_stats(pts, req.speed_kmh, req.op_hours_per_day, req.margin_pct, req.stop_hours),
            "note": "Great-circle distances on a sphere of radius 1,737.4 km. Straight-line estimate; ignores terrain."}


# ---------- favorites & plans ----------
@app.get("/api/favorites")
async def favorites(u=Depends(current_user)):
    return [r["site_id"] for r in await pool().fetch("SELECT site_id FROM favorites WHERE user_id=$1", u["id"])]


@app.put("/api/favorites/{site_id}", status_code=204)
async def add_fav(site_id: int, u=Depends(current_user)):
    try:
        await pool().execute("INSERT INTO favorites(user_id,site_id) VALUES($1,$2) ON CONFLICT DO NOTHING", u["id"], site_id)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(404, "Site not found")


@app.delete("/api/favorites/{site_id}", status_code=204)
async def del_fav(site_id: int, u=Depends(current_user)):
    await pool().execute("DELETE FROM favorites WHERE user_id=$1 AND site_id=$2", u["id"], site_id)


class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_site_id: Optional[int] = None
    waypoints: list[Waypoint] = Field(default_factory=list, max_length=50)
    params: dict = Field(default_factory=dict)
    distance_km: Optional[float] = Field(default=None, ge=0)
    duration_days: Optional[float] = Field(default=None, ge=0)


@app.get("/api/plans")
async def plans(u=Depends(current_user)):
    rows = await pool().fetch("SELECT id,name,start_site_id,waypoints,params,distance_km,duration_days,created_at "
                              "FROM mission_plans WHERE user_id=$1 ORDER BY id DESC", u["id"])
    return [dict(r) for r in rows]


@app.post("/api/plans", status_code=201)
async def create_plan(p: PlanIn, u=Depends(current_user)):
    try:
        pid = await pool().fetchval(
            "INSERT INTO mission_plans(user_id,name,start_site_id,waypoints,params,distance_km,duration_days) "
            "VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id", u["id"], p.name, p.start_site_id,
            [w.model_dump() for w in p.waypoints], p.params, p.distance_km, p.duration_days)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(404, "Start site not found")
    return {"id": pid}


@app.delete("/api/plans/{plan_id}", status_code=204)
async def delete_plan(plan_id: int, u=Depends(current_user)):
    await pool().execute("DELETE FROM mission_plans WHERE id=$1 AND user_id=$2", plan_id, u["id"])


# ---------- data sources & NASA proxy ----------
@app.get("/api/datasets")
async def datasets():
    return [dict(r) for r in await pool().fetch("SELECT name,description,url,status FROM data_sources ORDER BY id")]


_cache: dict = {}


@app.get("/api/nasa/search")
async def nasa_search(q: str = Query("lunar south pole", min_length=2, max_length=80), limit: int = Query(6, ge=1, le=20)):
    """Live proxy to the NASA Image and Video Library (public, no key needed), cached for 10 minutes."""
    key = (q.lower(), limit)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get("https://images-api.nasa.gov/search", params={"q": q, "media_type": "image"})
            r.raise_for_status()
            items = r.json()["collection"]["items"][:limit]
    except Exception as e:
        log.warning("NASA API failed: %s", e)
        raise HTTPException(503, "NASA API unavailable. The app falls back to clearly labeled sample data.")
    out = {"source": "NASA Image and Video Library (images-api.nasa.gov)",
           "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "query": q,
           "items": [{"title": i["data"][0].get("title"), "nasa_id": i["data"][0].get("nasa_id"),
                      "date_created": i["data"][0].get("date_created"),
                      "thumbnail": (i.get("links") or [{}])[0].get("href")} for i in items]}
    _cache[key] = (time.time(), out)
    return out


if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="web")
