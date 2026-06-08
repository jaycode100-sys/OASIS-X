# OASIS-X Desktop App

Two ways to use the desktop app:

## 1. Run directly (no build needed)

```powershell
pip install pywebview
python desktop_app.py
```

This starts the server in the background and opens a native OS window with the OASIS-X logo in the title bar. No browser needed. Closes cleanly when you close the window.

## 2. Build standalone .exe

```powershell
pip install pyinstaller pywebview
python build_desktop.py
```

### Output

```
dist\OASIS-X\OASIS-X.exe
```

Double-click `OASIS-X.exe` to launch the app as a standalone Windows program. The .exe has the OASIS-X icon (from `static/oasis.ico`) and opens as a native window — no browser tab, no console window.

### Requirements for the .exe

- **Windows 10+** with WebView2 Runtime (pre-installed on Windows 11)
- **Ollama** installed and running locally for LLM features (optional — rule-based fallback works without it)
- No Python installation needed — everything is bundled into the .exe

### Build notes

The first build takes 15–30 minutes because PyInstaller bundles sklearn, pandas, numpy, and scipy. Subsequent rebuilds with `--noconfirm` are faster.
