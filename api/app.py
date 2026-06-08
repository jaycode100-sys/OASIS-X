import logging
import os
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from api.routes import router
from api.auth import router as auth_router, seed_default_users
from data.database import init_db

app = FastAPI(
    title="OASIS-X",
    description=(
        "SWIFT Fault Healing System — Autonomous Predictive Fault Healing for Nigerian "
        "optical fibre networks. Models NCC QoS baselines, environmental patterns "
        "(harmattan, rain attenuation), generator failures, and time-of-day congestion "
        "for Lagos, Abuja, Port Harcourt, and Kano."
    ),
    version="1.0.0",
)

# CORS — allow browser requests from the same origin and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (dashboard UI)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# API routes
app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api", tags=["Pipeline"])


@app.get("/login", include_in_schema=False)
def login_page():
    """Serve the standalone login page."""
    login = os.path.join(STATIC_DIR, "login.html")
    if os.path.isfile(login):
        return FileResponse(login)
    return {"error": "login.html not found"}


@app.on_event("startup")
def startup():
    """Initialise database tables and seed default users on server start."""
    try:
        init_db()
        seed_default_users()
        logger.info("Startup complete — DB initialised, users seeded")
    except Exception as e:
        logger.critical(f"Startup failed: {e}")
        sys.exit(1)


@app.get("/", include_in_schema=False)
def home():
    """Serve the dashboard UI."""
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {
        "service": "SWIFT FHS",
        "status": "running",
        "docs": "/docs",
        "note": "Place index.html in static/ to serve the dashboard",
    }
