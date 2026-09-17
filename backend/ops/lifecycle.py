"""Run/batch/model-queue lifecycle: start, pause, resume, halt, threads."""

import json
import logging
import threading
import time
import uuid
from typing import Optional

import pandas as pd

from backend.database import Run, get_db

import backend.ops.state as _state  # noqa: E402
from backend.ops.state import (  # noqa: E402
    _halt_events,
    _batch_lock,
    _halt_events_lock,
    _active_threads,
    _active_threads_lock,
    MAX_CONCURRENT_RUNS,
    _run_slots,
)

from backend.ops.bench import (
    _build_run_params,
    _instantiate_benchmark,
    _make_client,
    _run_async,
)
from backend.ops.stats import (
    _build_batch_summary,
)

logger = logging.getLogger(__name__)


def _start_benchmark_thread(
    run_id: int,
    api_url: str,
    api_key: str,
    temp: float,
    max_tokens: int,
    sys_prompt: str,
    benchmark_name: str = "HumanEval",
    quick_test: Optional[bool] = None,
    _remaining_ids: Optional[list[int]] = None,
    context_length: Optional[int] = None,
):
    def _run():
        nonlocal quick_test
        with get_db() as db:
            try:
                run = db.query(Run).filter(Run.id == run_id).first()
                if not run:
                    logger.error(f"Run {run_id} not found for thread start.")
                    return
                params = run.get_parameters()
                # Provider keys are never persisted: they travel in memory
                # (thread args) so a copied database can't leak cloud keys.
                # The .pop also strips keys stored by older versions on rewrite.
                params.pop("api_key", None)
                if quick_test is None:
                    quick_test = params.get("quick_test", False)
                if temp is not None:
                    params.setdefault("temperature", temp)
                elif "temperature" in params:
                    del params["temperature"]
                params.setdefault("max_completion_tokens", max_tokens)
                params.setdefault("system_prompt", sys_prompt)
                if context_length is not None:
                    params.setdefault("context_length", context_length)
                with _halt_events_lock:
                    halt_ev = _halt_events.get(run_id)
                    if halt_ev is None:
                        halt_ev = threading.Event()
                        _halt_events[run_id] = halt_ev
                    # Clear any stale set-state left by a previous halt/skip so a
                    # resumed run doesn't instantly halt itself on the first check.
                    halt_ev.clear()
                params["_halt_event"] = halt_ev
                params_for_db = {k: v for k, v in params.items() if k != "_halt_event"}
                run.set_parameters(params_for_db)
                db.commit()

                client = _make_client(api_url, api_key)
                client._rep_disabled = params.get("disable_repetition_detection", False)
                bench = _instantiate_benchmark(benchmark_name, db, client, quick_test)
                try:
                    _run_async(bench.run_evaluation(run_id, params))
                finally:
                    _run_async(client.aclose())
            except Exception as e:
                logger.error(f"Benchmark thread fatal error: {e}", exc_info=True)
                try:
                    db.rollback()  # session may be in pending-rollback state after a failed commit
                    run = db.query(Run).filter(Run.id == run_id).first()
                    if run and run.status not in ("COMPLETED", "HALTED", "FAILED"):
                        run.status = "FAILED"
                        db.commit()
                except Exception as e_inner:
                    logger.warning(f"Failed to mark run as FAILED: {e_inner}")
        with _active_threads_lock:
            _active_threads.pop(run_id, None)
        with _halt_events_lock:
            _halt_events.pop(run_id, None)
        if _remaining_ids:
            _chain_batch(_remaining_ids, api_url, api_key, temp, max_tokens, sys_prompt, quick_test, context_length)

    with _active_threads_lock:
        existing = _active_threads.get(run_id)
        if existing and existing.is_alive():
            logger.warning(f"Run {run_id} already has an active thread — skipping duplicate start.")
            return None
    if not _run_slots.acquire(blocking=False):
        logger.warning(
            "Run %d rejected — %d concurrent runs already active (MAX_CONCURRENT_RUNS).",
            run_id, MAX_CONCURRENT_RUNS,
        )
        return None

    def _run_wrapped():
        try:
            _run()
        finally:
            _run_slots.release()

    thread = threading.Thread(target=_run_wrapped, daemon=True)
    with _active_threads_lock:
        existing = _active_threads.get(run_id)
        if existing and existing.is_alive():
            _run_slots.release()
            logger.warning(f"Run {run_id} already has an active thread — skipping duplicate start.")
            return None
        _active_threads[run_id] = thread
    thread.start()
    return thread


def _chain_batch(remaining_ids, api_url, api_key, temp, max_tokens, sys_prompt, quick_test, context_length=None):
    """When a batch run completes, finds the next PENDING run via _remaining_ids, resets halt_ev, and triggers it. Guarded by _batch_lock for _state._active_batch_id."""
    if not remaining_ids:
        # Batch fully chained — clear the active-batch marker so the UI
        # doesn't keep showing a stale "Batch N/N" card forever.
        with _batch_lock:
            _state._active_batch_id = None
            _state._batch_start_time = None
        return
    with _active_threads_lock:
        live = {rid for rid, t in _active_threads.items() if t.is_alive()}
    remaining_ids = [rid for rid in remaining_ids if rid not in live]
    if not remaining_ids:
        with _batch_lock:
            _state._active_batch_id = None
            _state._batch_start_time = None
        logger.warning("Batch chaining skipped — remaining runs already have active threads.")
        return
    next_run_id = remaining_ids[0]
    rest = remaining_ids[1:] if len(remaining_ids) > 1 else None
    with get_db() as db:
        run = db.query(Run).filter(Run.id == next_run_id).first()
        if not run:
            return
        # Prefer each chained run's own stored settings so resumed batches
        # continue with the connection config the run was originally created with.
        stored = run.get_parameters()
        api_url = stored.get("api_url") or api_url
        api_key = stored.get("api_key") or api_key
        temp = stored.get("temperature", temp)
        max_tokens = stored.get("max_completion_tokens", max_tokens)
        sys_prompt = stored.get("system_prompt", sys_prompt)
        bn = run.benchmark_name
        _start_benchmark_thread(
            next_run_id, api_url, api_key, temp, max_tokens, sys_prompt,
            benchmark_name=bn, quick_test=None, _remaining_ids=rest,
            context_length=context_length,
        )


def trigger_run(
    selected_model: str,
    benchmark_name: str,
    api_url: str,
    api_key: str = "",
    temp: float = 0.0,
    max_tokens: int = 2048,
    sys_prompt: str = "",
    quick_test: bool = False,
    disable_rep_detection: bool = False,
    context_length: Optional[int] = None,
) -> tuple[int | None, str]:
    """Start a single benchmark run.

    Creates a Run row in the database and spawns a daemon thread to execute the
    benchmark evaluation loop. The thread calls ``BaseBenchmark.run_evaluation()``
    which iterates over samples, generates completions, scores them, and writes
    Result rows incrementally.

    Args:
        selected_model: Model name or ID as recognized by the API provider.
        benchmark_name: One of the 29 registered benchmark names (e.g. "HumanEval").
        api_url: Full API base URL including /v1 (e.g. "http://127.0.0.1:1234/v1").
        api_key: API key for providers that require authentication (empty for local).
        temp: Sampling temperature. None omits the parameter (provider default).
        max_tokens: Maximum completion tokens per sample.
        sys_prompt: Optional system prompt prepended to each sample.
        quick_test: If True, use the 5-sample mini dataset instead of the full set.
        disable_rep_detection: If True, disable the anti-loop repetition detection.
        context_length: Optional context window length override.

    Returns:
        Tuple of (run_id, message). run_id is None on failure.
    """
    with get_db() as db:
        try:
            params_dict = _build_run_params(api_url, max_tokens, sys_prompt, temp, quick_test, disable_rep_detection, context_length)
            run = Run(
                model_name=selected_model,
                benchmark_name=benchmark_name,
                status="PENDING",
                parameters=json.dumps(params_dict),
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            run_id = run.id

            logger.info(
                "Triggering run %d: model=%s benchmark=%s temp=%s max_tokens=%d quick_test=%s batch=%s",
                run_id, selected_model, benchmark_name,
                f"{temp:.2f}" if temp is not None else "default",
                max_tokens, quick_test,
                "yes" if _state._active_batch_id else "no",
            )

            started = _start_benchmark_thread(
                run_id, api_url, api_key, temp, max_tokens, sys_prompt,
                benchmark_name=benchmark_name, quick_test=quick_test,
                context_length=context_length,
            )
            if started is None:
                # Either a duplicate thread (impossible for a fresh run_id)
                # or the concurrency cap refused the slot — the PENDING row
                # stays in the DB so the run can be resumed later.
                return run_id, (
                    f"Server busy — {MAX_CONCURRENT_RUNS} runs already active. "
                    f"Run {run_id} is saved as PENDING; resume it when a slot frees up."
                )
            return run_id, f"Run {run_id} started."
        except Exception as e:
            db.rollback()
            logger.error(f"trigger_run failed: {e}", exc_info=True)
            return None, str(e)


def start_batch(
    selected_model: str,
    selected_benchmarks: list[str],
    api_url: str,
    api_key: str = "",
    temp: float = 0.0,
    max_tokens: int = 2048,
    sys_prompt: str = "",
    quick_test: bool = False,
    disable_rep_detection: bool = False,
    context_length: Optional[int] = None,
) -> tuple[int | None, str, str, pd.DataFrame, str]:
    """Start a batch run — one model across multiple benchmarks sequentially.

    Creates one Run row per benchmark, all sharing a batch_id UUID. The first
    benchmark starts immediately; subsequent benchmarks are chained via
    ``_chain_next_batch_run()`` when each completes. Each Run stores its own
    api_url/api_key so resumes are independent.

    Args:
        selected_model: Model name or ID.
        selected_benchmarks: List of benchmark names to run in sequence.
        api_url: Full API base URL including /v1.
        api_key: API key for cloud providers.
        temp: Sampling temperature.
        max_tokens: Maximum completion tokens per sample.
        sys_prompt: Optional system prompt.
        quick_test: Use 5-sample mini datasets.
        disable_rep_detection: Disable anti-loop detection.
        context_length: Optional context window length override.

    Returns:
        Tuple of (first_run_id, batch_id, message, summary_df, batch_id_display).
    """
    if not selected_benchmarks:
        return None, "", "No benchmarks selected.", pd.DataFrame(), ""

    batch_id = str(uuid.uuid4())
    run_ids = []
    with get_db() as db:
        try:
            for bn in selected_benchmarks:
                params_dict = _build_run_params(api_url, max_tokens, sys_prompt, temp, quick_test, disable_rep_detection, context_length)
                run = Run(
                    model_name=selected_model,
                    benchmark_name=bn,
                    status="PENDING",
                    batch_id=batch_id,
                    parameters=json.dumps(params_dict),
                )
                db.add(run)
                db.commit()
                db.refresh(run)
                run_ids.append(run.id)

            with _batch_lock:
                _state._active_batch_id = batch_id
                _state._batch_start_time = time.time()

            summary_df = _build_batch_summary(batch_id)
            first_id = run_ids[0] if run_ids else None

            started = _start_benchmark_thread(
                run_ids[0], api_url, api_key, temp, max_tokens, sys_prompt,
                benchmark_name=selected_benchmarks[0], quick_test=quick_test,
                _remaining_ids=run_ids[1:] if len(run_ids) > 1 else None,
                context_length=context_length,
            )
            if started is None:
                return first_id, batch_id, (
                    f"Server busy — {MAX_CONCURRENT_RUNS} runs already active. "
                    f"Batch {batch_id[:8]} is saved as PENDING; resume run {first_id} when a slot frees up."
                ), summary_df, batch_id[:8]
            return first_id, batch_id, f"Batch {batch_id[:8]} started — {len(run_ids)} benchmarks.", summary_df, batch_id[:8]
        except Exception as e:
            db.rollback()
            logger.error(f"start_batch failed: {e}", exc_info=True)
            return None, "", str(e), pd.DataFrame(), ""


def pause_run(run_id: int) -> str:
    """Set a running benchmark to PAUSED status. The benchmark loop checks
    Run.status on every sample iteration and will stop processing until
    resumed. Only RUNNING runs can be paused."""
    with get_db() as db:
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                return "Run not found."
            if run.status != "RUNNING":
                return f"Cannot pause — status is {run.status}."
            run.status = "PAUSED"
            db.commit()
            return f"Run {run_id} paused."
        except Exception as e:
            logger.error(f"pause_run({run_id}) failed: {e}", exc_info=True)
            return str(e)


def resume_run(
    run_id: int,
    api_url: str = "",
    api_key: str = "",
    temp: Optional[float] = None,
    max_tokens: Optional[int] = None,
    sys_prompt: str = "",
    quick_test: Optional[bool] = None,
    disable_rep_detection: Optional[bool] = None,
    context_length: Optional[int] = None,
) -> str:
    """Resume a non-completed benchmark run from its saved current_index.

    Works for PAUSED, HALTED, FAILED, and PENDING runs — covering user halts and
    shutdown-interrupted runs (which are marked FAILED on server restart). Uses
    the run's stored parameters (api_url, temperature, max_tokens, quick_test)
    as the source of truth, so a one-click resume works without re-entering
    connection settings. If the run belongs to a regular batch, remaining
    non-terminal sibling runs (same model) are chained afterwards.
    """
    with get_db() as db:
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                return "Run not found."
            if run.status == "COMPLETED":
                return f"Cannot resume — run {run_id} is already COMPLETED."
            if run.status == "RUNNING":
                return f"Cannot resume — run {run_id} is currently RUNNING."

            stored = run.get_parameters()
            api_url = stored.get("api_url") or api_url
            api_key = stored.get("api_key") or api_key
            temp = stored.get("temperature", temp)
            max_tokens = stored.get("max_completion_tokens", max_tokens)
            sys_prompt = stored.get("system_prompt", sys_prompt)
            if quick_test is None:
                quick_test = stored.get("quick_test", False)
            if disable_rep_detection is None:
                disable_rep_detection = stored.get("disable_repetition_detection", False)

            remaining_ids = None
            if run.batch_id:
                siblings = (
                    db.query(Run.id)
                    .filter(
                        Run.batch_id == run.batch_id,
                        Run.id > run_id,
                        Run.model_name == run.model_name,
                        Run.status.in_(["PENDING", "HALTED", "FAILED", "PAUSED"]),
                    )
                    .order_by(Run.id)
                    .all()
                )
                if siblings:
                    with _active_threads_lock:
                        live = {rid for rid, t in _active_threads.items() if t.is_alive()}
                    remaining_ids = [s[0] for s in siblings if s[0] not in live]
                    if len(remaining_ids) != len(siblings):
                        logger.warning(
                            f"Run {run_id} resume: {len(siblings) - len(remaining_ids)} sibling(s) already "
                            "have active threads — those will not be re-chained."
                        )
                    if remaining_ids:
                        with _batch_lock:
                            _state._active_batch_id = run.batch_id
                            _state._batch_start_time = time.time()

            previous_status = run.status
            run.status = "RUNNING"
            stored_params = run.get_parameters()
            stored_params["disable_repetition_detection"] = disable_rep_detection
            if context_length is not None:
                stored_params["context_length"] = context_length
            run.set_parameters(stored_params)
            db.commit()
            with _halt_events_lock:
                halt_ev = _halt_events.get(run_id)
                if halt_ev is None:
                    halt_ev = threading.Event()
                    _halt_events[run_id] = halt_ev
                # Stale events left set by a previous halt/skip would instantly
                # re-halt the resumed run — clear before starting.
                halt_ev.clear()

            result = _start_benchmark_thread(
                run_id, api_url, api_key, temp, max_tokens, sys_prompt,
                benchmark_name=run.benchmark_name, quick_test=quick_test,
                _remaining_ids=remaining_ids, context_length=context_length,
            )
            if result is None:
                # Thread rejected (duplicate active thread) — restore previous status
                run.status = previous_status
                db.commit()
                return f"Run {run_id} could not resume — a thread is already active."
            msg = f"Run {run_id} resumed."
            if remaining_ids:
                msg += f" Continuing batch {run.batch_id[:8]} — {len(remaining_ids)} remaining benchmark(s)."
            return msg
        except Exception as e:
            logger.error(f"resume_run failed for run {run_id}: {e}", exc_info=True)
            return str(e)


def halt_run(run_id: int) -> str:
    """Permanently stop a benchmark run. Sets the halt event (so the
    benchmark thread exits its loop) and updates the DB status to HALTED.
    Unlike pause, a halted run cannot be resumed — a new run must be started."""
    with get_db() as db:
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                return "Run not found."
            with _halt_events_lock:
                halt_ev = _halt_events.get(run_id)
                if halt_ev:
                    halt_ev.set()
            run.status = "HALTED"
            db.commit()
            return f"Run {run_id} halted."
        except Exception as e:
            logger.error(f"halt_run({run_id}) failed: {e}", exc_info=True)
            return str(e)


def update_run_notes(run_id: int, notes: str) -> str:
    """Update a run's notes field (service layer).

    Raises :class:`RunNotFoundError` when the run does not exist.
    """
    from backend.ops.errors import RunNotFoundError

    with get_db() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise RunNotFoundError(run_id)
        run.notes = notes or ""
        db.commit()
        return run.notes
