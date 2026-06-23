import logging
import sys

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

# ── Static files ──
STATIC_DIR = __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "static")
if __import__("os").path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Global exception handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details."},
    )


# ── Routes ──
from api.routes import router  # noqa: E402
from api.auth import router as auth_router, seed_default_users  # noqa: E402
from data.database import init_db  # noqa: E402

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api", tags=["Pipeline"])


# ── Page routes ──
@app.get("/login", include_in_schema=False)
def login_page():
    login = __import__("os").path.join(STATIC_DIR, "login.html")
    if __import__("os").path.isfile(login):
        return FileResponse(login)
    return JSONResponse(status_code=404, content={"detail": "login.html not found"})


@app.get("/", include_in_schema=False)
def home():
    landing = __import__("os").path.join(STATIC_DIR, "landing.html")
    if __import__("os").path.isfile(landing):
        return FileResponse(landing)
    index = __import__("os").path.join(STATIC_DIR, "index.html")
    if __import__("os").path.isfile(index):
        return FileResponse(index)
    return {
        "service": "SWIFT FHS",
        "status": "running",
        "docs": "/docs",
        "note": "Place index.html in static/ to serve the dashboard",
    }


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    index = __import__("os").path.join(STATIC_DIR, "index.html")
    if __import__("os").path.isfile(index):
        return FileResponse(index)
    return JSONResponse(status_code=404, content={"detail": "index.html not found"})


# ── Startup ──
@app.on_event("startup")
def startup():
    try:
        init_db()
        seed_default_users()
        logger.info("Startup complete — DB initialised, users seeded")
    except Exception as e:
        logger.critical("Startup failed: %s", e)
        sys.exit(1)
