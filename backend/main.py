import logging, json, os, sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

ENABLE_DIAG = False
ROOT = Path(__file__).parent.parent

# In PyInstaller .exe builds, assets live next to the exe or in sys._MEIPASS
_meipass = getattr(sys, '_MEIPASS', None)
if _meipass and (Path(_meipass) / "frontend" / "dist").exists():
    FRONTEND_DIST = Path(_meipass) / "frontend" / "dist"
elif (ROOT / "frontend" / "dist").exists():
    FRONTEND_DIST = ROOT / "frontend" / "dist"
else:
    # Fallback: look beside the executable
    exe_dir = Path(sys.argv[0]).parent if getattr(sys, 'frozen', False) else ROOT
    FRONTEND_DIST = exe_dir / "frontend" / "dist"
    if not FRONTEND_DIST.exists():
        FRONTEND_DIST = exe_dir  # try the exe directory itself

app = FastAPI(
    title="BenchMax Core Engine",
    description="Backend coordinator for local LLM performance and correctness evaluations",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

try:
    logger.info("Initializing BenchMax SQLite database...")
    init_db()
    from backend.database import SessionLocal, Run
    db = SessionLocal()
    try:
        stale = db.query(Run).filter(Run.status == "RUNNING").all()
        for r in stale:
            logger.warning(f"Marking stale running run #{r.id} ({r.benchmark_name}) as FAILED (server restart)")
            r.status = "FAILED"
        db.commit()
        if stale:
            logger.info(f"Marked {len(stale)} stale run(s) as FAILED")
    finally:
        db.close()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.error(f"Critical error initializing database: {e}")
    raise

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": "BenchMax", "database": "connected"}

import threading
@app.get("/api/shutdown")
def shutdown():
    def _die():
        import os, time
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_die, daemon=True).start()
    return {"status": "shutting_down"}

# Register all REST API routes from api.py
from backend.api import router as api_router
app.include_router(api_router, prefix="/api")

# Diagnostic endpoints
if ENABLE_DIAG:
    @app.get("/api/diag/telemetry")
    def diag_telemetry():
        from backend.operations import telemetry_history, MAX_HISTORY_LEN, _EMA_ALPHA
        return {
            "len": len(telemetry_history),
            "max": MAX_HISTORY_LEN,
            "ema_alpha": _EMA_ALPHA,
            "samples": telemetry_history[-50:] if telemetry_history else [],
        }

# Serve frontend static files
if FRONTEND_DIST.exists():
    logger.info(f"Serving frontend from {FRONTEND_DIST}")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"error": "Frontend not built"}

    @app.get("/assets/{file_path:path}", include_in_schema=False)
    async def serve_assets(file_path: str):
        asset = FRONTEND_DIST / "assets" / file_path
        if asset.exists() and asset.is_file():
            return FileResponse(str(asset))
        return {"error": "Asset not found"}

    # SPA fallback: only for non-API paths
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("static/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Not found"}, status_code=404)
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"error": "Frontend not built"}
else:
    logger.warning(f"Frontend dist not found at {FRONTEND_DIST}. Run: cd frontend && npm run build")
