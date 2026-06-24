@echo off
REM ── OASIS-X Desktop Build Script ──
REM Prerequisites: pip install pyinstaller, Inno Setup installed
echo ========================================
echo   OASIS-X Desktop Build
echo ========================================
echo.

echo [1/3] Building executable with PyInstaller...
pyinstaller oasis-x.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo BUILD FAILED — check PyInstaller output
    exit /b 1
)
echo   ✓ Executable built: dist\OASIS-X\OASIS-X.exe
echo.

echo [2/3] Creating installer with Inno Setup...
where iscc >nul 2>&1
if %errorlevel% equ 0 (
    iscc installer.iss
    if %errorlevel% equ 0 (
        echo   ✓ Installer created: installer\Output\OASIS-X-Setup.exe
    ) else (
        echo   ✗ Inno Setup failed — you can still use the dist\ folder directly
    )
) else (
    echo   ℹ Inno Setup not found — skipping installer creation
    echo   Download from: https://jrsoftware.org/isinfo.php
    echo   Then run: iscc installer.iss
)
echo.

echo [3/3] Done!
echo   Portable:  dist\OASIS-X\OASIS-X.exe
echo   Installer: installer\Output\OASIS-X-Setup.exe
echo.
pause
