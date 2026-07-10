@echo off
chcp 65001 >nul
title BenchMax Build

echo ========================================
echo   BenchMax - Build Script
echo ========================================
echo.

:: 1. Setup virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating Python virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create venv. Make sure Python 3.11+ is installed.
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment exists, skipping.
)

:: 2. Install dependencies
echo [2/4] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt -q
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    exit /b 1
)

:: 3. Install PyInstaller
echo [3/4] Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo ERROR: Failed to install PyInstaller.
    exit /b 1
)

:: 4. Build the executable
echo [4/4] Building BenchMax.exe...
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
