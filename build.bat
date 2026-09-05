@echo off
chcp 65001 >nul
title BenchMax Build
cd /d "%~dp0"

echo ========================================
echo   BenchMax - Build Script
echo ========================================
echo.
echo TIP: If this window closes on its own, re-run from a terminal
echo      with:  cmd /c build.bat
echo      so the error message stays visible.
echo.

:: 1. Setup virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating Python virtual environment...
    python -m venv .venv
    rem NOTE: use IF ERRORLEVEL here, not percent-errorlevel checks,
    rem because percent variables expand too early inside parens.
    if errorlevel 1 (
        echo ERROR: Failed to create venv. Make sure Python 3.11+ is installed.
        pause
        exit /b 1
    )
) else (
    echo [1/5] Virtual environment exists, skipping.
)

:: 2. Install dependencies
echo [2/5] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt -q
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: 3. Build frontend
echo [3/5] Building frontend...
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js/npm not found. Install Node 22+ from https://nodejs.org/
    pause
    exit /b 1
)
cd /d "%~dp0frontend"
call npm ci --silent
if %errorlevel% neq 0 (
    echo WARNING: npm ci failed, trying npm install...
    call npm install --silent
    rem NOTE: same early-expansion rule as step 1, use IF ERRORLEVEL here.
    if errorlevel 1 (
        echo ERROR: npm install failed. Check your network and Node.js install.
        cd /d "%~dp0"
        pause
        exit /b 1
    )
)
call npm run build
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed.
    cd /d "%~dp0"
    pause
    exit /b 1
)
if not exist "dist\index.html" (
    echo ERROR: Frontend dist not created, dist\index.html is missing.
    cd /d "%~dp0"
    pause
    exit /b 1
)
cd /d "%~dp0"

:: 4. Install PyInstaller - skip if already present
echo [4/5] Checking PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [4/5] Installing PyInstaller...
    ".venv\Scripts\python.exe" -m pip install pyinstaller -q
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install PyInstaller.
        pause
        exit /b 1
    )
) else (
    echo [4/5] PyInstaller already installed, skipping.
)

:: 5. Build the executable
echo [5/5] Building BenchMax.exe...
".venv\Scripts\python.exe" -m PyInstaller benchmax.spec --clean
if %errorlevel% neq 0 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)
if not exist "dist\BenchMax.exe" (
    echo ERROR: PyInstaller finished but dist\BenchMax.exe was not created.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build complete!
for %%I in ("dist\BenchMax.exe") do echo   Output: dist\BenchMax.exe - %%~zI bytes
echo ========================================
pause
