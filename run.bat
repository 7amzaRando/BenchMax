@echo off
chcp 65001 >nul
title BenchMax - Local LLM Benchmarker
echo.
echo ========================================
echo   BenchMax - Local LLM Benchmarker
echo   http://localhost:8000/
echo ========================================
echo.

set PYTHONPATH=%~dp0

%~dp0.venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 8000
