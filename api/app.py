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


@app.get("/status", include_in_schema=False)
def status_page():
    path = _os.path.join(STATIC_DIR, "status.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "status.html not found"})


@app.get("/signup", include_in_schema=False)
def signup_page():
    path = _os.path.join(STATIC_DIR, "signup.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "signup.html not found"})


@app.get("/blog", include_in_schema=False)
def blog_page():
    path = _os.path.join(STATIC_DIR, "blog.html")
    if _os.path.isfile(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "blog.html not found"})


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
        from data.database import DB_PATH, DB_DIR
        logger.info("Startup complete — DB initialised, users seeded")
        logger.info("DB_DIR  = %s (exists=%s)", DB_DIR, _os.path.isdir(DB_DIR))
        logger.info("DB_PATH = %s (exists=%s, size=%s bytes)", DB_PATH, _os.path.isfile(DB_PATH), _os.path.getsize(DB_PATH) if _os.path.isfile(DB_PATH) else "N/A")
        logger.info("STATIC_DIR = %s (exists=%s)", STATIC_DIR, _os.path.isdir(STATIC_DIR))
        for f in ["landing.html", "index.html", "login.html", "cases.html"]:
            logger.info("  %s: %s", f, _os.path.isfile(_os.path.join(STATIC_DIR, f)))
        # Auto-start Ollama if not running (non-blocking)
        import threading
        threading.Thread(target=_ensure_ollama, daemon=True).start()
        # Start Telegram polling
        from api.notifications import start_telegram_polling
        start_telegram_polling()
    except Exception as e:
        logger.critical("Startup failed: %s", e)
        sys.exit(1)


def _ensure_ollama():
    """Start Ollama if not already running."""
    import urllib.request, urllib.error, subprocess
    ollama_host = _os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    # Check if already running
    try:
        urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=3)
        logger.info("Ollama already running at %s", ollama_host)
        return
    except Exception:
        pass
    # Find executable
    candidates = [
        _os.environ.get("OLLAMA_EXE", ""),
        r"C:\Users\USER\AppData\Local\Programs\Ollama\ollama.exe",
        "/usr/local/bin/ollama",
        "/usr/bin/ollama",
    ]
    exe = None
    for c in candidates:
        if c and _os.path.isfile(c):
            exe = c
            break
    if not exe:
        exe = "ollama"
    logger.info("Starting Ollama from %s ...", exe)
    try:
        kwargs = {"stdout": _os.devnull, "stderr": _os.devnull}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen([exe, "serve"], **kwargs)
    except Exception as e:
        logger.warning("Could not start Ollama: %s — LLM features disabled", e)
        return
    # Wait up to 15s
    import time
    for i in range(15):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=3)
            logger.info("Ollama ready (took %ds)", i + 1)
            return
        except Exception:
            pass
    logger.warning("Ollama not reachable after 15s")
