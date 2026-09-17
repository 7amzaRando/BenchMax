"""Multi-model queue: load → run → unload → next (sequential)."""

import json
import logging
import threading
import time
import uuid
from typing import Optional

from sqlalchemy.orm import joinedload

from backend.database import Run, get_db

import backend.ops.state as _state  # noqa: E402
from backend.ops.state import (  # noqa: E402
    _halt_events,
    _batch_lock,
    _halt_events_lock,
    _model_queue_state,
    _model_queue_lock,
)

from backend.ops.bench import (
    _instantiate_benchmark,
    _make_client,
    _run_async,
)
from backend.ops.stats import (
    _build_token_stats_str,
    _compute_result_stats,
)

logger = logging.getLogger(__name__)



def _queue_skip_model_requested() -> bool:
    with _model_queue_lock:
        return _model_queue_state.get("skip_model", False)


def _clear_skip_model_flag():
    with _model_queue_lock:
        _model_queue_state["skip_model"] = False


def _queue_halted() -> bool:
    """Check if the model queue has been halted (thread-safe)."""
    with _model_queue_lock:
        return _model_queue_state["status"] == "halted"


def _run_model_queue_in_thread(
    queue_id: str,
    model_benchmarks: list[tuple[str, list[str]]],
    api_url: str,
    api_key: str,
    temp: float,
    max_tokens: int,
    sys_prompt: str,
    quick_test: bool,
    disable_rep_detection: bool = False,
    context_length: Optional[int] = None,
):
    """
    Loops through (model, benchmarks) pairs: loads model via LM Studio API, runs all benchmarks
    sequentially, then unloads model. Checks halt at 3 points (between models, after load, between
    benchmarks). Captures instance_id from load response for unload.
    """

    client = _make_client(api_url, api_key)

    with _model_queue_lock:
        _model_queue_state["queue_id"] = queue_id
        _model_queue_state["models"] = [m for m, _ in model_benchmarks]
        _model_queue_state["total_models"] = len(model_benchmarks)
        _model_queue_state["status"] = "running"
        _model_queue_state["api_url"] = api_url
        _model_queue_state["api_key"] = api_key

    try:
        for mi, (model_id, benches) in enumerate(model_benchmarks):
            if _queue_halted():
                break
            # A skip requested while the previous model was unloading should
            # move on to the NEXT model — not end the whole queue.
            if _queue_skip_model_requested():
                _clear_skip_model_flag()
                with _model_queue_lock:
                    _model_queue_state["current_benchmark"] = f"Skipping {model_id}..."
                continue

            with _model_queue_lock:
                _model_queue_state["current_model_index"] = mi
                _model_queue_state["current_benchmark"] = f"Loading {model_id}..."

            # Load model
            try:
                load_result = _run_async(client.load_model(model_id))
                if load_result.get("error") or load_result.get("status_code", 200) >= 400:
                    err = load_result.get("error") or f"HTTP {load_result.get('status_code')}: {load_result.get('body', '')}"
                    logger.error(f"Model load failed for {model_id}: {err}")
                    with _model_queue_lock:
                        _model_queue_state["status"] = "failed"
                        _model_queue_state["message"] = f"Failed to load {model_id}: {err}"
                    return
                time.sleep(2)
            except Exception as e:
                logger.error(f"Model load exception for {model_id}: {e}")
                with _model_queue_lock:
                    _model_queue_state["status"] = "failed"
                    _model_queue_state["message"] = f"Failed to load {model_id}: {e}"
                return

            if _queue_halted():
                try:
                    _run_async(client.unload_model(model_id))
                except Exception as e2:
                    logger.warning(f"Error unloading model {model_id}: {e2}")
                break

            # Create Run records for each benchmark on this model
            with get_db() as db:
                run_ids_for_model = []
                for bn in benches:
                    mparams = {"api_url": api_url, "max_completion_tokens": max_tokens, "system_prompt": sys_prompt}
                    if temp is not None:
                        mparams["temperature"] = temp
                    mparams["quick_test"] = quick_test
                    mparams["disable_repetition_detection"] = disable_rep_detection
                    if context_length is not None:
                        mparams["context_length"] = context_length
                    run = Run(
                        model_name=model_id,
                        benchmark_name=bn,
                        status="PENDING",
                        batch_id=queue_id,
                        parameters=json.dumps(mparams),
                    )
                    db.add(run)
                    db.commit()
                    db.refresh(run)
                    run_ids_for_model.append(run.id)

            with _model_queue_lock:
                _model_queue_state["current_benchmark"] = f"Running on {model_id}"
                _model_queue_state["benchmarks_per_model"][model_id] = benches

            # Run benchmarks sequentially on this model
            for bi, bn in enumerate(benches):
                if _queue_halted():
                    break
                # NOTE: do NOT clear the skip flag here — clearing at iteration
                # start races with a user click during the previous benchmark's
                # completion window and silently drops the skip. The flag is
                # only consumed below (and after the model unloads).

                with _model_queue_lock:
                    _model_queue_state["current_benchmark"] = f"{model_id} — {bn} ({bi+1}/{len(benches)})"
                    _model_queue_state["run_id"] = run_ids_for_model[bi]

                with get_db() as db2:
                    try:
                        run_rec = db2.query(Run).filter(Run.id == run_ids_for_model[bi]).first()
                        if not run_rec:
                            logger.error(f"Run {run_ids_for_model[bi]} not found")
                            continue
                        params = run_rec.get_parameters()
                        if temp is not None:
                            params["temperature"] = temp
                        elif "temperature" in params:
                            del params["temperature"]
                        params["max_completion_tokens"] = max_tokens
                        params["system_prompt"] = sys_prompt
                        params.pop("api_key", None)  # never persist provider keys (see _start_benchmark_thread)
                        with _halt_events_lock:
                            halt_ev = _halt_events.get(run_rec.id)
                            if halt_ev is None:
                                halt_ev = threading.Event()
                                _halt_events[run_rec.id] = halt_ev
                        params["_halt_event"] = halt_ev
                        params_for_db = {k: v for k, v in params.items() if k != "_halt_event"}
                        run_rec.set_parameters(params_for_db)
                        db2.commit()

                        client._rep_disabled = params.get("disable_repetition_detection", False)
                        bench = _instantiate_benchmark(bn, db2, client, quick_test)
                        _run_async(bench.run_evaluation(run_rec.id, params))
                    except Exception as e:
                        logger.error(f"Model queue benchmark error ({model_id} / {bn}): {e}", exc_info=True)
                        try:
                            run_rec_err = db2.query(Run).filter(Run.id == run_ids_for_model[bi]).first()
                            if run_rec_err and run_rec_err.status not in ("COMPLETED", "HALTED", "FAILED"):
                                run_rec_err.status = "FAILED"
                                db2.commit()
                        except Exception as e3:
                            logger.warning(f"Error marking run {run_ids_for_model[bi]} as FAILED: {e3}")

                # After each benchmark, skip remaining benchmarks on this model if requested
                if _queue_skip_model_requested():
                    _clear_skip_model_flag()
                    break

            # Unload model (only if not halted — halt has its own cleanup)
            if not _queue_halted():
                with _model_queue_lock:
                    _model_queue_state["current_benchmark"] = f"Unloading {model_id}..."
                    _model_queue_state.pop("run_id", None)
                try:
                    _run_async(client.unload_model(model_id))
                    time.sleep(1)
                except Exception as unload_err:
                    logger.warning(f"Model unload warning for {model_id}: {unload_err}")
                _clear_skip_model_flag()

        # All models done or skipped/halted — set terminal state
        _was_halted = _queue_halted()
        with _model_queue_lock:
            if _model_queue_state["status"] == "halted":
                _model_queue_state["message"] = "Model queue halted."
            elif _model_queue_state["status"] != "failed":
                _model_queue_state["status"] = "completed"
                _model_queue_state["message"] = f"All {len(model_benchmarks)} model(s) completed."
    finally:
        # Halt cleanup: unload current model, reset global state
        if _queue_halted():
            model_to_unload = None
            api_url_halt = "http://127.0.0.1:1234/v1"
            api_key_halt = ""
            with _model_queue_lock:
                idx = _model_queue_state.get("current_model_index", 0)
                models = _model_queue_state["models"]
                if idx < len(models):
                    model_to_unload = models[idx]
                api_url_halt = _model_queue_state.get("api_url", api_url_halt)
                api_key_halt = _model_queue_state.get("api_key", "")
            if model_to_unload:
                try:
                    halt_client = _make_client(api_url_halt, api_key_halt)
                    _run_async(halt_client.unload_model(model_to_unload))
                    logger.info(f"Halt cleanup: unloaded model {model_to_unload}")
                except Exception as e:
                    logger.warning(f"Halt cleanup: unload of {model_to_unload} failed: {e}")
            with _model_queue_lock:
                _model_queue_state["status"] = "idle"
                _model_queue_state["queue_id"] = None
                _model_queue_state.pop("run_id", None)
            with _batch_lock:
                _state._active_batch_id = None
                _state._batch_start_time = None
        elif _model_queue_state.get("status") == "failed":
            # A load error killed the queue — mark leftover PENDING runs as
            # FAILED so they're not stuck in limbo, then reset to idle so a
            # new queue can start (previously the state stayed "failed" forever).
            qid = _model_queue_state.get("queue_id")
            if qid:
                with get_db() as db_f:
                    try:
                        leftover = db_f.query(Run).filter(
                            Run.batch_id == qid,
                            Run.status == "PENDING",
                        ).all()
                        for lr in leftover:
                            lr.status = "FAILED"
                        if leftover:
                            db_f.commit()
                            logger.info(f"Model queue failed: marked {len(leftover)} leftover run(s) as FAILED.")
                    except Exception as e_f:
                        logger.error(f"Model queue failed-cleanup DB error: {e_f}")
            with _model_queue_lock:
                _model_queue_state["status"] = "idle"
                _model_queue_state["queue_id"] = None
                _model_queue_state.pop("run_id", None)
            with _batch_lock:
                _state._active_batch_id = None
                _state._batch_start_time = None
        try:
            _run_async(client.aclose())
        except Exception as e_close:
            logger.warning(f"Error closing HTTP client: {e_close}")


def start_model_queue(
    model_benchmarks: list[tuple[str, list[str]]],
    api_url: str,
    api_key: str = "",
    temp: float = 0.0,
    max_tokens: int = 2048,
    sys_prompt: str = "",
    quick_test: bool = False,
    disable_rep_detection: bool = False,
    context_length: Optional[int] = None,
) -> tuple[str, str]:
    """Start a model queue — multiple models, each running all benchmarks sequentially.

    For each model: load via LM Studio API → run all benchmarks → unload.
    State tracked in ``_model_queue_state`` dict. Halt sets all PENDING/RUNNING
    runs to HALTED and unloads the current model.

    Args:
        model_benchmarks: List of (model_id, [benchmark_names]) tuples.
        api_url: LM Studio / API base URL.
        api_key: API key for cloud providers.
        temp: Sampling temperature.
        max_tokens: Maximum completion tokens.
        sys_prompt: Optional system prompt.
        quick_test: Use 5-sample mini datasets.
        disable_rep_detection: Disable anti-loop detection.
        context_length: Optional context window length override.

    Returns:
        Tuple of (queue_id, message).
    """
    if not model_benchmarks:
        return "", "No models selected."

    queue_id = str(uuid.uuid4())
    total_models = len(model_benchmarks)
    total_benches = sum(len(b) for _, b in model_benchmarks)

    thread = threading.Thread(
        target=_run_model_queue_in_thread,
        args=(queue_id, model_benchmarks, api_url, api_key, temp, max_tokens, sys_prompt, quick_test, disable_rep_detection, context_length),
        daemon=True,
    )
    thread.start()

    return queue_id, f"Model queue started — {total_models} model(s), {total_benches} benchmark(s)."


def get_model_queue_state() -> dict:
    """Get the current state of the model queue.

    Returns:
        dict with keys: queue_id, models, current_model_index, total_models,
        current_benchmark, status, message, live stats (accuracy, tps, tokens, etc.).
    """
    with _model_queue_lock:
        state = dict(_model_queue_state)
    run_id = state.get("run_id")
    if run_id and state.get("status") in ("running", "completed", "failed"):
        with get_db() as db:
            run = db.query(Run).options(joinedload(Run.results)).filter(Run.id == run_id).first()
            if run:
                progress = run.current_index or 0
                try:
                    from backend.benchmarks.base import get_live_progress
                    live = get_live_progress(run.id)
                    if live is not None and live > progress:
                        progress = live
                except Exception:
                    pass
                state["sample_progress"] = progress
                state["total_samples"] = run.total_samples or 0
                results = run.results
                if results:
                    stats = _compute_result_stats(results)
                    state["accuracy"] = f"{stats['accuracy']}%"
                    state["avg_tps"] = stats["avg_tps"]
                    state["avg_ttft"] = stats["avg_ttft"]
                    state["token_stats"] = _build_token_stats_str(stats)
    return state


def halt_model_queue() -> str:
    """Halt the currently running model queue and unload the active model.

    Returns:
        str: Status message ("Halted model queue." or "No active model queue.").
    """
    qid = None
    with _model_queue_lock:
        if _model_queue_state["status"] not in ("running", "pending"):
            return "No active model queue."
        _model_queue_state["status"] = "halted"
        _model_queue_state["message"] = "Model queue halting — finishing current sample..."
        qid = _model_queue_state["queue_id"]
    if qid:
        with get_db() as db:
            try:
                runs = db.query(Run).filter(
                    Run.batch_id == qid,
                    Run.status.in_(["RUNNING", "PENDING"]),
                ).all()
                with _halt_events_lock:
                    for r in runs:
                        halt_ev = _halt_events.get(r.id)
                        if halt_ev:
                            halt_ev.set()
                        r.status = "HALTED"
                db.commit()
            except Exception as e:
                logger.error(f"halt_model_queue DB error: {e}")
    return "Model queue halted — cleaning up..."


def skip_current_model() -> str:
    """Skip the currently running model and advance to the next in the queue.

    Returns:
        str: Status message ("Skipped." or "No active model queue.").
    """
    with _model_queue_lock:
        if _model_queue_state["status"] != "running":
            return "No active model queue."
        _model_queue_state["skip_model"] = True
        _model_queue_state["message"] = "Skipping current model..."
        qid = _model_queue_state.get("queue_id")
    if qid:
        with get_db() as db:
            try:
                run = db.query(Run).filter(
                    Run.batch_id == qid,
                    Run.status == "RUNNING",
                ).first()
                if run:
                    with _halt_events_lock:
                        halt_ev = _halt_events.get(run.id)
                        if halt_ev:
                            halt_ev.set()
                    run.status = "HALTED"
                    db.commit()
            except Exception as e:
                logger.error(f"skip_current_model DB error: {e}")
    return "Skipping current model..."
