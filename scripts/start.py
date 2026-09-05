#!/usr/bin/env python3
"""Launches BenchMax backend (serves pre-built frontend from frontend/dist/)."""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent
VENV = ROOT / ".venv" / "Scripts"

print("=" * 50)
print("  BenchMax — Local LLM Benchmarker")
print("  http://localhost:8000")
print("=" * 50)
print()

cmd = [str(VENV / "uvicorn.exe"), "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
subprocess.run(cmd, cwd=str(ROOT))
