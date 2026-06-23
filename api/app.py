import logging
import sys
import os as _os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import settings

# ── Structured logging ──
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("oasis-x")

# ── App factory ──
app = FastAPI(
    title="OASIS-X",
    description=(
        "SWIFT Fault Healing System — Autonomous Predictive Fault Healing for Nigerian "
        "optical fibre networks. Models NCC QoS baselines, environmental patterns "
        "(harmattan, rain attenuation), generator failures, and time-of-day congestion "
        "for Lagos, Abuja, Port Harcourt, and Kano."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static dir ──
_APP_DIR = _os.path.dirname(_os.path.abspath(__file__))
STATIC_DIR = _os.path.normpath(_os.path.join(_APP_DIR, "..", "static"))

# ── API routes (registered FIRST) ──
from api.routes import router  # noqa: E402
from api.auth import router as auth_router, seed_default_users  # noqa: E402
from data.database import init_db  # noqa: E402

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api", tags=["Pipeline"])

# ── Page routes (registered BEFORE static mount) ──
@app.get("/", include_in_schema=False)
def home():
    path = _os.path.join(STATIC_DIR, "landing.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    path = _os.path.join(STATIC_DIR, "index.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return {"service": "SWIFT FHS", "status": "running", "docs": "/docs"}


@app.get("/landing", include_in_schema=False)
def landing():
    path = _os.path.join(STATIC_DIR, "landing.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "landing.html not found"})


@app.get("/login", include_in_schema=False)
def login_page():
    path = _os.path.join(STATIC_DIR, "login.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "login.html not found"})


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    path = _os.path.join(STATIC_DIR, "index.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "index.html not found"})


@app.get("/cases", include_in_schema=False)
def cases_page():
    path = _os.path.join(STATIC_DIR, "cases.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "cases.html not found"})


# ── Static files mount (MUST be LAST — mounts are catch-all) ──
if _os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Global exception handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details."},
    )

# ── Startup ──
@app.on_event("startup")
def startup():
    try:
        init_db()
        seed_default_users()
        logger.info("Startup complete — DB initialised, users seeded")
        logger.info("STATIC_DIR = %s (exists=%s)", STATIC_DIR, _os.path.isdir(STATIC_DIR))
        for f in ["landing.html", "index.html", "login.html", "cases.html"]:
            logger.info("  %s: %s", f, _os.path.isfile(_os.path.join(STATIC_DIR, f)))
    except Exception as e:
        logger.critical("Startup failed: %s", e)
        sys.exit(1)
