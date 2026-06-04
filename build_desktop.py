"""
OASIS-X Desktop Build Script
=============================
Packages the full OASIS-X application into a standalone Windows .exe using PyInstaller.

Usage:
    pip install pyinstaller
    python build_desktop.py

Output: dist/OASIS-X/OASIS-X.exe
"""
import os, sys, shutil, site
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
SPEC = ROOT / "OASIS-X.spec"

# Ensure PyInstaller is available
try:
    import PyInstaller
except ImportError:
    print("PyInstaller not found. Install with: pip install pyinstaller")
    sys.exit(1)

# Clean previous builds
for d in [DIST, ROOT / "build"]:
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)

# ── Hidden imports (PyInstaller doesn't auto-detect these) ──
HIDDEN = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.middleware.wsgi",
    "passlib.handlers.bcrypt",
    "bcrypt",
    "jose",
    "jose.backends.cryptography_backend",
    "sklearn",
    "sklearn.ensemble",
    "sklearn.tree",
    "sklearn.neighbors",
    "sklearn.preprocessing",
    "pandas",
    "numpy",
    "requests",
    "multipart",
]

# ── Data files to bundle ──
DATA = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "models"), "models"),
    (str(ROOT / ".env.example"), "."),
]

# ── Generate .spec and build ──
import PyInstaller.__main__

PyInstaller.__main__.run([
    "--name=OASIS-X",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--add-data", f"{ROOT / 'static'}{os.pathsep}static",
    "--add-data", f"{ROOT / 'models'}{os.pathsep}models",
    "--add-data", f"{ROOT / '.env.example'}{os.pathsep}.",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--hidden-import=uvicorn.protocols.websockets.auto",
    "--hidden-import=passlib.handlers.bcrypt",
    "--hidden-import=bcrypt",
    "--hidden-import=jose",
    "--hidden-import=jose.backends.cryptography_backend",
    "--hidden-import=sklearn",
    "--hidden-import=sklearn.ensemble",
    "--hidden-import=sklearn.tree",
    "--hidden-import=sklearn.neighbors",
    "--hidden-import=pandas",
    "--hidden-import=numpy",
    "--hidden-import=requests",
    "--hidden-import=multipart",
    "--hidden-import=webview",
    str(ROOT / "desktop_app.py"),
])

print("\nBuild complete!")
print(f"Output: {DIST / 'OASIS-X' / 'OASIS-X.exe'}")
print("\nNOTE: The .exe requires:")
print("  - Windows 10+ with WebView2 Runtime (pre-installed on Win11)")
print("  - Ollama installed and running for LLM features")
print("  - Run: dist\\OASIS-X\\OASIS-X.exe")
