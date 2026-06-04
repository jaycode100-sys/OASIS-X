"""OASIS-X Desktop Application — starts the server and opens a native webview window."""
import os, sys, threading, webbrowser
from pathlib import Path

# Ensure we're in the project root
os.chdir(Path(__file__).resolve().parent)

def start_server():
    import uvicorn
    PORT = int(os.environ.get("PORT", "8080"))
    HOST = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("api.app:app", host=HOST, port=PORT, log_level="warning")

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", "8080"))

    # Start the server in a background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # Wait for the server to be ready
    import requests, time
    for _ in range(30):
        try:
            r = requests.get(f"http://127.0.0.1:{PORT}/api/status", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)

    # Open webview window
    try:
        import webview
        webview.create_window("OASIS-X", f"http://127.0.0.1:{PORT}/login", width=1280, height=800, resizable=True)
        webview.start()
    except ImportError:
        print(f"PyWebView not installed. Open http://127.0.0.1:{PORT}/login in your browser.")
        webbrowser.open(f"http://127.0.0.1:{PORT}/login")
        t.join()
