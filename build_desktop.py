"""
OASIS-X Desktop Build Script
=============================
Packages OASIS-X into a standalone Windows .exe with native app behaviour.

Usage:
    pip install pyinstaller pywebview
    python build_desktop.py

Output: dist\OASIS-X\OASIS-X.exe
"""
import os, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
ICON = ROOT / "static" / "oasis.ico"

# Check prerequisites
for mod, label in [("PyInstaller", "pyinstaller"), ("webview", "pywebview")]:
    try:
        __import__(mod)
    except ImportError:
        print(f"{mod} not found. Install with: pip install {label}")
        sys.exit(1)

if not ICON.exists():
    print(f"Icon not found: {ICON}")
    print("Run this first to generate it:")
    print("  python -c \"from PIL import Image; img=Image.open('static/oasis.png'); sz=min(img.size); left=(img.width-sz)//2; top=(img.height-sz)//2; img=img.crop((left,top,left+sz,top+sz)); img.save('static/oasis.ico', format='ICO', sizes=[(s,s) for s in [16,32,48,64,128,256]], append_images=[img.resize((s,s), Image.LANCZOS) for s in [16,32,48,64,128,256]])\"")
    sys.exit(1)

# Clean previous builds
for d in [DIST, ROOT / "build"]:
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)

# Prepare resource paths for PyInstaller
sep = os.pathsep

import PyInstaller.__main__

PyInstaller.__main__.run([
    "--name=OASIS-X",
    "--onefile",
    "--windowed",          # no console window
    "--noconfirm",
    "--clean",
    f"--icon={ICON}",
    # Exclude scipy (~200MB, not used at runtime)
    "--exclude-module=scipy",
    "--exclude-module=scipy.spatial",
    "--exclude-module=scipy.linalg",
    "--exclude-module=scipy.special",
    "--exclude-module=scipy.stats",
    "--exclude-module=scipy.sparse",
    "--exclude-module=matplotlib",
    # Bundle static assets
    f"--add-data={ROOT / 'static'}{sep}static",
    f"--add-data={ROOT / 'models'}{sep}models",
    f"--add-data={ROOT / '.env.example'}{sep}.",
    # Hidden imports (PyInstaller can't auto-detect these)
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--hidden-import=uvicorn.protocols.websockets.auto",
    "--hidden-import=uvicorn.middleware.wsgi",
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

print()
print("=" * 55)
print("  BUILD COMPLETE!")
print("=" * 55)
print(f"  .exe location: {DIST / 'OASIS-X.exe'}")
print()
print("  REQUIREMENTS:")
print("  - Windows 10+ with WebView2 Runtime")
print("    (pre-installed on Windows 11, or get it at:")
print("     https://developer.microsoft.com/microsoft-edge/webview2/)")
print("  - Ollama installed & running for LLM features")
print()
print("  RUN IT:")
print(f"    {DIST / 'OASIS-X.exe'}")
print()
print("  The app opens as a native window with the OASIS-X icon")
print("  in the taskbar and title bar. No browser needed.")
