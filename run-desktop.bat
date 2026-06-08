@echo off
REM OASIS-X Desktop Launcher — run directly (no build needed)
pip show pywebview >NUL 2>&1 || pip install pywebview
start "" python desktop_app.py
echo OASIS-X is starting in a native window...
