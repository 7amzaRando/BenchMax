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
        from backend.sandbox.docker_executor import _docker_available
        return _docker_available()
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

def _queue_skip_model_requested() -> bool:
    with _model_queue_lock:
        return _model_queue_state.get("skip_model", False)

def _clear_skip_model_flag() -> None:
    with _model_queue_lock:
        _model_queue_state["skip_model"] = False

def _queue_halted() -> bool:
    with _model_queue_lock:
        return _model_queue_state.get("status") == "halted"
