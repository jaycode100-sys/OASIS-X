"""OASIS-X Desktop Application — native window (not browser)."""
import os, sys, threading, webbrowser, time
from pathlib import Path

# Determine root directory (handles both source and PyInstaller bundle)
if getattr(sys, 'frozen', False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent

os.chdir(ROOT)

# Set database directory to user's AppData so data persists across launches
if not os.environ.get("OASIS_DB_DIR"):
    appdata = Path(os.environ.get("APPDATA", ROOT)) / "OASIS-X"
    os.environ["OASIS_DB_DIR"] = str(appdata)

def start_server():
    import uvicorn
    PORT = int(os.environ.get("PORT", "8080"))
    HOST = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("api.app:app", host=HOST, port=PORT, log_level="warning")

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", "8080"))

    # Start the server in a background daemon thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # Wait for the server to be ready
    import requests
    for _ in range(30):
        try:
            r = requests.get(f"http://127.0.0.1:{PORT}/api/status", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)

    # Open as a native application window (not a browser tab)
    try:
        import webview
        # When built with PyInstaller (--icon flag), the .exe carries the
        # OASIS-X icon; the webview window inherits it.
        webview.create_window(
            "OASIS-X",
            f"http://127.0.0.1:{PORT}/",
            width=1280,
            height=800,
            resizable=True,
        )
        webview.start()
    except ImportError:
        print("PyWebView not installed. Install with: pip install pywebview")
        print(f"Falling back to browser at http://127.0.0.1:{PORT}/")
        webbrowser.open(f"http://127.0.0.1:{PORT}/")
        t.join()
