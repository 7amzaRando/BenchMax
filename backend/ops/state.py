"""Shared mutable state for operations — single source of truth.

Extracted from backend/operations.py:27-63 to break the 2307L god-file.
All queue/batch/telemetry globals live here; other ops modules import from here
to avoid circular `from backend.operations import X` cycles.
"""
import threading

MAX_HISTORY_LEN = 300
telemetry_history: list[dict] = []
_active_batch_id: str | None = None
_batch_start_time: float | None = None

def _docker_daemon_running() -> bool:
    """Check if Docker daemon is available and running."""
    try:
        from backend.sandbox.docker_executor import is_docker_available
        return is_docker_available()
    except Exception:
        return False

_halt_events: dict[int, threading.Event] = {}
_EMA_ALPHA = 0.15
_LB_SUPABASE_KEY = ""
_LB_API_URL = "https://bcbrrsghpynsvsxdsrjn.supabase.co/rest/v1/leaderboard"
_batch_lock = threading.Lock()
_halt_events_lock = threading.Lock()
_telemetry_lock = threading.Lock()
_active_threads: dict[int, threading.Thread] = {}
_active_threads_lock = threading.Lock()
_ema_state: dict = {"cpu": 0.0, "gpu": 0.0}

_model_queue_state: dict = {
    "queue_id": None,
    "models": [],
    "current_model_index": 0,
    "total_models": 0,
    "benchmarks_per_model": {},
    "current_benchmark": "",
    "status": "idle",
    "message": "",
    "skip_model": False,
}
_model_queue_lock = threading.RLock()

# --- Concurrency cap -------------------------------------------------------
# BenchMax is a single-process local app: every run spawns a daemon thread.
# The semaphore bounds that growth so a batch/model-queue accident can't
# spawn unbounded threads. Callers treat a refused acquire as "server busy".
MAX_CONCURRENT_RUNS = 4
_run_slots = threading.Semaphore(MAX_CONCURRENT_RUNS)

# --- Single-source mutation helpers --------------------------------------
# Scalar/list rebinds MUST go through these (or direct ``_state.X = ...``
# attribute writes). Bare ``from ... import X`` + ``X = ...`` in another
# module would fork a second binding and silently split the state.


def set_active_batch(batch_id: str | None, start_time: float | None = None) -> None:
    """Set the active batch marker (thread-safe)."""
    global _active_batch_id, _batch_start_time
    with _batch_lock:
        _active_batch_id = batch_id
        _batch_start_time = start_time


def clear_active_batch() -> None:
    """Clear the active batch marker (thread-safe)."""
    set_active_batch(None, None)


def get_active_batch() -> tuple[str | None, float | None]:
    """Return (batch_id, start_time) snapshot (thread-safe)."""
    with _batch_lock:
        return _active_batch_id, _batch_start_time


def append_telemetry(entry: dict) -> None:
    """Append a telemetry sample, capping the ring in place (thread-safe).

    In-place cap (``del``) keeps the list object identity stable so
    ``from backend.ops.state import telemetry_history`` holders never fork.
    """
    global telemetry_history
    with _telemetry_lock:
        telemetry_history.append(entry)
        overflow = len(telemetry_history) - MAX_HISTORY_LEN
        if overflow > 0:
            del telemetry_history[:overflow]

def _queue_skip_model_requested() -> bool:
    with _model_queue_lock:
        return _model_queue_state.get("skip_model", False)

def _clear_skip_model_flag() -> None:
    with _model_queue_lock:
        _model_queue_state["skip_model"] = False

def _queue_halted() -> bool:
    with _model_queue_lock:
        return _model_queue_state.get("status") == "halted"
