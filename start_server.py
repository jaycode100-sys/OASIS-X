import os, sys, subprocess, time, logging

os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("start_server")

# ── Ollama auto-start ──────────────────────────────────────────────────────────
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_EXE = os.environ.get("OLLAMA_EXE", "")  # auto-detected if empty

def _find_ollama() -> str:
    """Locate the ollama executable."""
    if OLLAMA_EXE and os.path.isfile(OLLAMA_EXE):
        return OLLAMA_EXE
    # Common install paths
    for candidate in [
        r"C:\Users\USER\AppData\Local\Programs\Ollama\ollama.exe",
        "/usr/local/bin/ollama",
        "/usr/bin/ollama",
        os.path.expanduser("~/AppData/Local/Programs/Ollama/ollama.exe"),
    ]:
        if os.path.isfile(candidate):
            return candidate
    # Hope it's on PATH
    return "ollama"


def _ollama_running() -> bool:
    """Check if Ollama is reachable."""
    import urllib.request, urllib.error
    try:
        req = urllib.request.Request(OLLAMA_HOST, method="GET")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        return False


def _start_ollama():
    """Start the Ollama serve process in the background."""
    exe = _find_ollama()
    log.info("Starting Ollama from %s ...", exe)
    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        log.warning("Ollama executable not found at %s — LLM features disabled", exe)
        return
    except Exception as e:
        log.warning("Could not start Ollama: %s", e)
        return

    # Wait up to 30s for Ollama to become reachable
    for i in range(30):
        time.sleep(1)
        if _ollama_running():
            log.info("Ollama is ready (took %ds)", i + 1)
            return
    log.warning("Ollama started but not reachable after 30s — LLM features may be unavailable")


def _ensure_models():
    """Pull the base model and create custom models if they don't exist."""
    import urllib.request, json

    if not _ollama_running():
        return

    # Check which models exist
    try:
        resp = urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5)
        data = json.loads(resp.read())
        existing = {m["name"].split(":")[0] for m in data.get("models", [])}
    except Exception:
        existing = set()

    exe = _find_ollama()
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    # Pull base model if missing
    if "llama3.2" not in existing:
        log.info("Pulling llama3.2:1b base model (this may take a few minutes)...")
        try:
            subprocess.run(
                [exe, "pull", "llama3.2:1b"],
                creationflags=creationflags,
                timeout=600,
            )
        except Exception as e:
            log.warning("Failed to pull llama3.2:1b: %s", e)
            return

    # Create custom models if missing
    modelfiles = {
        "swift-fhs": os.path.join("models", ".ollama", "Modelfile"),
        "nexus-chat": os.path.join("models", ".ollama", "ChatModelfile"),
    }
    for model_name, modelfile_path in modelfiles.items():
        if model_name not in existing:
            full_path = os.path.abspath(modelfile_path)
            if os.path.isfile(full_path):
                log.info("Creating model %s from %s ...", model_name, full_path)
                try:
                    subprocess.run(
                        [exe, "create", model_name, "-f", full_path],
                        creationflags=creationflags,
                        timeout=300,
                    )
                except Exception as e:
                    log.warning("Failed to create %s: %s", model_name, e)
            else:
                log.warning("Modelfile not found: %s", full_path)


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Auto-start Ollama if not running
    if not _ollama_running():
        _start_ollama()
    else:
        log.info("Ollama already running")

    # Ensure models are available
    _ensure_models()

    import uvicorn

    PORT = int(os.environ.get("PORT", os.environ.get("SERVER_PORT", "8080")))
    HOST = os.environ.get("HOST", "0.0.0.0")

    log.info("Starting OASIS-X server on %s:%s", HOST, PORT)
    uvicorn.run("api.app:app", host=HOST, port=PORT)
