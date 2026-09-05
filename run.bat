@echo off
chcp 65001 >nul
title BenchMax - Local LLM Benchmarker
echo.
echo ========================================
echo   BenchMax - Local LLM Benchmarker
echo   http://localhost:8000/
echo ========================================
echo.

set "PYTHONPATH=%~dp0"

if not exist "%~dp0.venv\Scripts\uvicorn.exe" (
    echo ERROR: Virtual environment not found at .venv\Scripts\uvicorn.exe
    echo        Run build.bat first to set up the environment.
    pause
    exit /b 1
)

set "BENCHMAX_HOST=%BENCHMAX_HOST%"
if "%BENCHMAX_HOST%"=="" set "BENCHMAX_HOST=127.0.0.1"
set "BENCHMAX_PORT=%BENCHMAX_PORT%"
if "%BENCHMAX_PORT%"=="" set "BENCHMAX_PORT=8000"
set "BENCHMAX_RELOAD=%BENCHMAX_RELOAD%"
if "%BENCHMAX_RELOAD%"=="" set "BENCHMAX_RELOAD=0"

if "%BENCHMAX_RELOAD%"=="1" (
    "%~dp0.venv\Scripts\uvicorn.exe" backend.main:app --reload --host "%BENCHMAX_HOST%" --port "%BENCHMAX_PORT%"
) else (
    "%~dp0.venv\Scripts\uvicorn.exe" backend.main:app --host "%BENCHMAX_HOST%" --port "%BENCHMAX_PORT%"
)
