import logging
import os
import sys
import secrets as _secrets
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.logging_setup import configure_logging
configure_logging()
logger = logging.getLogger(__name__)

from backend.database import init_db, get_db  # noqa: E402
from backend.api import SafeJSONResponse  # noqa: E402

ENABLE_DIAG = False
ROOT = Path(__file__).parent.parent
_admin_token = _secrets.token_hex(16)

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
    version="2.0.1",
    default_response_class=SafeJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.responses import JSONResponse as _JSONResponse  # noqa: E402


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth headers on every response (localhost app, no cookies
    to steal — still worth having if ever bound to LAN)."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


class _LanAuthMiddleware(BaseHTTPMiddleware):
    """Un-skippable LAN gate: loopback clients pass freely; any client
    arriving over the network must present a valid Bearer token issued
    via POST /api/auth/login. Health + auth endpoints stay open so the
    login screen can detect state and authenticate."""

    _OPEN_PREFIXES = ("/api/health", "/api/auth/")

    async def dispatch(self, request, call_next):
        from backend import auth as lan_auth
        path = request.url.path
        if path.startswith(self._OPEN_PREFIXES):
            return await call_next(request)
        # The SPA shell (HTML/JS/CSS) must load so the login screen can
        # render — it carries no data. All data flows through /api/*,
        # which is gated below.
        if not path.startswith("/api/"):
            return await call_next(request)
        if not lan_auth.lan_request_allowed(request):
            return _JSONResponse({"detail": "LAN login required."}, status_code=401)
        return await call_next(request)


app.add_middleware(_SecurityHeadersMiddleware)
app.add_middleware(_LanAuthMiddleware)

# BenchMax is a single-process app: batch/queue/halt/progress state lives in
# process-local memory (backend/ops/state.py) with a bounded run-slot
# semaphore (MAX_CONCURRENT_RUNS). Do NOT serve with multiple workers
# (e.g. ``uvicorn --workers 4``) — each worker would split that state and
# pause/halt/queue commands would only reach one worker's runs.
if os.environ.get("BENCHMAX_WORKERS", "") not in ("", "1"):
    logger.warning(
        "BENCHMAX_WORKERS=%s — BenchMax requires a single worker; "
        "batch/queue/halt state will split across workers.",
        os.environ.get("BENCHMAX_WORKERS"),
    )

try:
    logger.info("Initializing BenchMax SQLite database...")
    init_db()
    from backend.database import Run
    with get_db() as db:
        stale = db.query(Run).filter(Run.status == "RUNNING").all()
        for r in stale:
            logger.warning(f"Marking stale running run #{r.id} ({r.benchmark_name}) as FAILED (server restart)")
            r.status = "FAILED"
        db.commit()
        if stale:
            logger.info(f"Marked {len(stale)} stale run(s) as FAILED")
    logger.info("Database initialized successfully. Admin shutdown token set (shown in startup output only).")
except Exception as e:
    logger.error(f"Critical error initializing database: {e}")
    raise

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": "BenchMax", "database": "connected"}

import threading  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class _ShutdownBody(BaseModel):
    token: str = ""


@app.post("/api/shutdown")
async def shutdown(request: Request, body: _ShutdownBody | None = None):
    """Shut down the server. The token travels in the JSON body (never the
    URL, so it stays out of logs). Empty token is accepted from localhost
    only; LAN callers already passed the Bearer gate above, and a wrong
    non-empty token is always rejected."""
    token = ""
    if body is not None:
        token = body.token or ""
    if not token:
        # Back-compat: older CLI/frontend versions send ?token= in the URL.
        token = request.query_params.get("token", "")
    if token and token != _admin_token:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    def _die():
        import sys
        import time
        time.sleep(0.6)
        # Only kill the reloader parent when --reload is active; otherwise
        # ppid is the cmd.exe running run.bat and killing it triggers the
        # "Terminate batch job (Y/N)?" prompt.
        if os.environ.get("BENCHMAX_RELOAD") == "1":
            try:
                import signal
                import subprocess
                ppid = os.getppid()
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(ppid), "/T", "/F"], capture_output=True, timeout=2)
                else:
                    os.kill(ppid, signal.SIGTERM)
            except Exception:
                pass
        os._exit(0)
    threading.Thread(target=_die, daemon=True).start()
    return {"status": "shutting_down"}

# Register all REST API routes from api.py
from backend.api import router as api_router  # noqa: E402
app.include_router(api_router, prefix="/api")
# API versioning: /api/* is frozen (back-compat). /api/v1/* serves the same
# router so new clients can pin a versioned base path; new breaking
# endpoints go under /api/v2. Excluded from OpenAPI schema to avoid
# duplicate operation IDs in /docs.
app.include_router(api_router, prefix="/api/v1", include_in_schema=False)

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
        candidate = (FRONTEND_DIST / "assets" / file_path).resolve()
        dist_root = FRONTEND_DIST.resolve()
        if candidate.is_relative_to(dist_root) and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return {"error": "Asset not found"}

    # SPA fallback: only for non-API paths
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("static/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Not found"}, status_code=404)
        # Resolve + containment check: prevents ..\ traversal from escaping
        # the frontend dist dir into records/benchmax.db, .hf_token, etc.
        candidate = (FRONTEND_DIST / full_path).resolve()
        dist_root = FRONTEND_DIST.resolve()
        if candidate.is_relative_to(dist_root) and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"error": "Frontend not built"}
else:
    logger.warning(f"Frontend dist not found at {FRONTEND_DIST}. Run: cd frontend && npm run build")
