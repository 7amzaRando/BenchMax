@echo off
chcp 65001 >nul
title BenchMax Build

echo ========================================
echo   BenchMax - Build Script
echo ========================================
echo.

:: 1. Setup virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating Python virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create venv. Make sure Python 3.11+ is installed.
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
    exit /b 1
)

:: 3. Build frontend
echo [3/5] Building frontend...
cd /d "%~dp0frontend"
call npm ci --silent
if %errorlevel% neq 0 (
    echo WARNING: npm ci failed, trying npm install...
    call npm install --silent
)
call npm run build
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed.
    exit /b 1
)
cd /d "%~dp0"

:: 4. Install PyInstaller
echo [4/5] Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo ERROR: Failed to install PyInstaller.
    exit /b 1
)

:: 5. Build the executable
echo [5/5] Building BenchMax.exe...
".venv\Scripts\python.exe" -m PyInstaller benchmax.spec --clean
if %errorlevel% neq 0 (
    echo ERROR: Build failed.
    exit /b 1
)

echo.
echo ========================================
echo   Build complete!
for %%I in ("dist\BenchMax.exe") do echo   Output: dist\BenchMax.exe (%%~zI bytes)
echo ========================================
pause
