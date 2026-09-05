import html as html_mod
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import secrets
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import httpx
from sqlalchemy import func as sa_func, cast as sa_cast, case as sa_case, Integer as sa_Integer, Float as sa_Float
from sqlalchemy.orm import joinedload, load_only

from backend.config import ROOT, EXE_DIR, BENCHMARKS, BENCH_NAMES, DATASETS, PROVIDER_PRESETS
from backend.database import Run, Result, get_db
from backend.telemetry.monitor import get_system_metrics

logger = logging.getLogger(__name__)

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

# Model queue state
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


def _clear_skip_model_flag():
    with _model_queue_lock:
        _model_queue_state["skip_model"] = False


def _update_telemetry_history() -> tuple[dict, float, float]:
    """Append a smoothed telemetry sample to the history ring buffer.

    EMA state lives in the module-level `_ema_state` dict so smoothing
    survives across API calls (the previous parameter-passing approach
    discarded the smoothed values on every call, making the EMA inert).
    """
    global telemetry_history
    metrics = get_system_metrics()
    raw_cpu = metrics.get("cpu_percent", 0.0)
    raw_gpu = metrics.get("gpu_load", 0.0)
    with _telemetry_lock:
        prev_cpu = _ema_state["cpu"]
        prev_gpu = _ema_state["gpu"]
        smooth_cpu = prev_cpu + _EMA_ALPHA * (raw_cpu - prev_cpu) if prev_cpu else raw_cpu
        smooth_gpu = prev_gpu + _EMA_ALPHA * (raw_gpu - prev_gpu) if prev_gpu else raw_gpu
        _ema_state["cpu"] = smooth_cpu
        _ema_state["gpu"] = smooth_gpu
        entry = {
            "timestamp": time.time(),
            "cpu_percent": smooth_cpu,
            "ram_used_gb": metrics.get("ram_used_gb", 0.0),
            "ram_total_gb": metrics.get("ram_total_gb", 0.0),
            "gpu_load": smooth_gpu,
            "vram_used_mb": metrics.get("vram_used_mb", 0.0),
            "vram_total_mb": metrics.get("vram_total_mb", 0.0),
        }
        telemetry_history.append(entry)
        if len(telemetry_history) > MAX_HISTORY_LEN:
            telemetry_history = telemetry_history[-MAX_HISTORY_LEN:]
    return metrics, smooth_cpu, smooth_gpu


def _add_scoring_columns(row: dict, result) -> dict:
    row = dict(row)
    if result.scoring_details:
        try:
            extra = json.loads(result.scoring_details)
            if isinstance(extra, dict):
                for k, v in extra.items():
                    if k not in row:
                        row[k] = v
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse scoring_details for result %s", getattr(result, 'id', '?'))
    return row


def _stored_result_category(result) -> str | None:
    """Category recorded in a result's scoring_details (None if absent)."""
    if result.scoring_details:
        try:
            extra = json.loads(result.scoring_details)
            if isinstance(extra, dict):
                cat = extra.get("category")
                if cat and cat != "unknown":
                    return str(cat)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _sample_category_for_benchmark(sample: dict, benchmark_name: str) -> str | None:
    """Derive a sample's category the same way current benchmark code does,
    so backfilled old runs match what new runs record in scoring_details."""
    if benchmark_name == "LiveCodeBench":
        return sample.get("difficulty") or None
    if benchmark_name == "Aider Polyglot":
        return sample.get("language") or None
    for key in ("category", "topic", "domain", "subject"):
        val = sample.get(key)
        if isinstance(val, str) and val and val != "unknown":
            return val
    return None


def _backfill_category_map(benchmark_name: str, db, task_ids: list[str]) -> dict[str, str]:
    """Map task_id → category from the dataset for results that predate
    per-question category tracking (e.g. old LiveCodeBench/Aider runs whose
    scoring_details lack 'category'). Returns {} on any failure (dataset
    removed, redesigned, or genuinely single-category like HumanEval)."""
    try:
        bench = _instantiate_benchmark(benchmark_name, db, None)
        dataset = bench.load_dataset()
    except Exception:
        return {}
    wanted = set(task_ids)
    cat_by_id: dict[str, str] = {}
    for s in dataset:
        if not isinstance(s, dict):
            continue
        cat = _sample_category_for_benchmark(s, benchmark_name)
        if not cat:
            continue
        for key in (s.get("task_id"), s.get("question_id"), s.get("key")):
            if isinstance(key, str) and key in wanted:
                cat_by_id[key] = cat
    return cat_by_id


def _compute_run_stats_sql(db, run_id: int) -> dict:
    """Compute aggregate result statistics for a single run via SQL."""
    batch = _compute_batch_stats_sql(db, [run_id])
    return batch.get(run_id, {
        "tps_vals": [], "ttft_vals": [], "prompt_tps_vals": [],
        "total_tk": 0, "think_tk": 0, "resp_tk": 0,
        "avg_tps": 0.0, "avg_ttft": 0.0, "avg_prompt_tps": 0.0,
        "avg_tokens": 0, "accuracy": 0.0, "correct": 0, "total": 0,
    })


def _compute_batch_stats_sql(db, run_ids: list[int]) -> dict[int, dict]:
    """Compute aggregate stats for multiple runs in a single SQL query (avoids N+1)."""
    if not run_ids:
        return {}
    rows = db.query(
        Result.run_id,
        sa_func.count(Result.id).label("total"),
        sa_func.sum(sa_cast(Result.correct, sa_Integer)).label("correct"),
        sa_func.avg(sa_case((Result.tps > 0, Result.tps), else_=None)).label("avg_tps"),
        sa_func.avg(sa_case((Result.ttft > 0, Result.ttft), else_=None)).label("avg_ttft"),
        sa_func.avg(sa_case(
            (Result.ttft > 0, sa_cast(Result.prompt_tokens, sa_Float) / Result.ttft),
            else_=None
        )).label("avg_prompt_tps"),
        sa_func.sum(sa_func.coalesce(Result.thinking_tokens, 0) + sa_func.coalesce(Result.response_tokens, 0)).label("total_tk"),
        sa_func.sum(sa_func.coalesce(Result.thinking_tokens, 0)).label("think_tk"),
        sa_func.sum(sa_func.coalesce(Result.response_tokens, 0)).label("resp_tk"),
    ).filter(Result.run_id.in_(run_ids)).group_by(Result.run_id).all()
    result = {}
    for row in rows:
        total = row.total or 0
        correct = row.correct or 0
        result[row.run_id] = {
            "tps_vals": [], "ttft_vals": [], "prompt_tps_vals": [],
            "total_tk": int(row.total_tk or 0), "think_tk": int(row.think_tk or 0), "resp_tk": int(row.resp_tk or 0),
            "avg_tps": round(float(row.avg_tps), 1) if row.avg_tps else 0.0,
            "avg_ttft": round(float(row.avg_ttft), 1) if row.avg_ttft else 0.0,
            "avg_prompt_tps": round(float(row.avg_prompt_tps), 1) if row.avg_prompt_tps else 0.0,
            "avg_tokens": round(int(row.total_tk or 0) / total, 1) if total else 0,
            "accuracy": round(correct / total * 100, 1) if total else 0.0,
            "correct": correct, "total": total,
        }
    # Fill in missing run_ids (no results yet) with empty stats
    for rid in run_ids:
        if rid not in result:
            result[rid] = {
                "tps_vals": [], "ttft_vals": [], "prompt_tps_vals": [],
                "total_tk": 0, "think_tk": 0, "resp_tk": 0,
                "avg_tps": 0.0, "avg_ttft": 0.0, "avg_prompt_tps": 0.0,
                "avg_tokens": 0, "accuracy": 0.0, "correct": 0, "total": 0,
            }
    return result


def _compute_run_progress(run, stats=None) -> dict:
    total = run.total_samples or 1
    current = run.current_index or 0
    # Prefer the in-memory per-sample counter (fresher than the batched DB
    # commit) so live progress moves every sample, not every 5/25.
    try:
        from backend.benchmarks.base import get_live_progress
        live = get_live_progress(run.id)
        if live is not None and live > current:
            current = live
    except Exception:
        pass
    if stats is None:
        results = run.results
        stats = _compute_result_stats(results) if results else None
    return {
        "prog_val": min(current / total, 1.0),
        "status_md": f"**{run.benchmark_name}** — {run.status}  ({current}/{total})",
        "active_task": run.benchmark_name,
        "avg_tps": stats["avg_tps"] if stats else 0.0,
        "avg_ttft": stats["avg_ttft"] if stats else 0.0,
        "avg_prompt_tps": stats["avg_prompt_tps"] if stats else 0.0,
        "accuracy": f"{stats['accuracy']}%" if stats else "",
        "token_stats": _build_token_stats_str(stats) if stats else "",
    }


def _build_token_stats_str(stats: dict) -> str:
    think_pct = round(stats["think_tk"] / stats["total_tk"] * 100, 1) if stats["total_tk"] else 0.0
    resp_pct = round(stats["resp_tk"] / stats["total_tk"] * 100, 1) if stats["total_tk"] else 0.0
    return f"Think: {think_pct}% | Resp: {resp_pct}% | Total: {stats['total_tk']}"


def _result_to_export_dict(r) -> dict:
    row = {
        "run_id": r.run_id,
        "task_id": r.task_id,
        "correct": r.correct,
        "elapsed_time": r.elapsed_time,
        "tps": r.tps,
        "ttft": r.ttft,
        "prompt_tokens": r.prompt_tokens,
        "thinking_tokens": r.thinking_tokens,
        "response_tokens": r.response_tokens,
        "error_message": r.error_message,
        "prompt": r.prompt,
        "raw_response": r.raw_response,
        "extracted_code": r.extracted_code,
    }
    return _add_scoring_columns(row, r)


def _compute_result_stats(results):
    """Compute aggregate statistics from a list of Result objects.
    Single-pass over results for O(N) instead of O(6N).
    Returns a dict with tps_vals, ttft_vals, total_tk, think_tk, resp_tk,
    avg_tps, avg_ttft, avg_prompt_tps, avg_tokens, accuracy.
    Handles empty results gracefully."""
    tps_vals = []
    ttft_vals = []
    prompt_tps_vals = []
    total_tk = 0
    think_tk = 0
    resp_tk = 0
    correct = 0
    total = len(results)
    for r in results:
        if r.tps and r.tps > 0:
            tps_vals.append(r.tps)
        if r.ttft and r.ttft > 0:
            ttft_vals.append(r.ttft)
        if r.ttft and r.ttft > 0 and r.prompt_tokens and r.prompt_tokens > 0:
            prompt_tps_vals.append(r.prompt_tokens / r.ttft)
        t = (r.thinking_tokens or 0) + (r.response_tokens or 0)
        total_tk += t
        think_tk += r.thinking_tokens or 0
        resp_tk += r.response_tokens or 0
        if r.correct:
            correct += 1
    return {
        "tps_vals": tps_vals,
        "ttft_vals": ttft_vals,
        "prompt_tps_vals": prompt_tps_vals,
        "total_tk": total_tk,
        "think_tk": think_tk,
        "resp_tk": resp_tk,
        "avg_tps": round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0.0,
        "avg_ttft": round(sum(ttft_vals) / len(ttft_vals), 1) if ttft_vals else 0.0,
        "avg_prompt_tps": round(sum(prompt_tps_vals) / len(prompt_tps_vals), 1) if prompt_tps_vals else 0.0,
        "avg_tokens": round(total_tk / total, 1) if total else 0,
        "accuracy": round(correct / total * 100, 1) if total else 0.0,
        "correct": correct,
        "total": total,
    }


def _build_run_params(api_url, max_tokens, sys_prompt, temp, quick_test, disable_rep_detection, context_length=None):
    """Build the standard params dict stored in Run.parameters."""
    params = {"api_url": api_url, "max_completion_tokens": max_tokens, "system_prompt": sys_prompt}
    if temp is not None:
        params["temperature"] = temp
    params["quick_test"] = quick_test
    params["disable_repetition_detection"] = disable_rep_detection
    if context_length is not None:
        params["context_length"] = context_length
    return params


def _make_client(api_url: str, api_key: str):
    from backend.lm_studio.client import LMStudioClient
    return LMStudioClient(base_url=api_url, api_key=api_key or None)


def _run_async(coro):
    """Run an async coroutine from sync code with a fresh event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except RuntimeError:
            pass


BENCHMARK_CLASSES = {
    "HumanEval": ("backend.benchmarks.humaneval", "HumanEvalBenchmark"),
    "MMLU-Pro": ("backend.benchmarks.mmlu_pro", "MMLUProBenchmark"),
    "IFEval": ("backend.benchmarks.ifeval", "IFEvalBenchmark"),
    "AIME": ("backend.benchmarks.aime", "AIMEBenchmark"),
    "BigCodeBench": ("backend.benchmarks.bigcodebench", "BigCodeBenchBenchmark"),
    "BigCodeBench-Hard": ("backend.benchmarks.bigcodebench", "BigCodeBenchBenchmark"),
    "BFCL": ("backend.benchmarks.bfcl", "BFCLBenchmark"),
    "UncensorBench": ("backend.benchmarks.uncensor", "UncensorBenchBenchmark"),
    "LongBench-v2": ("backend.benchmarks.longbench_v2", "LongBenchV2Benchmark"),
    "Aider Polyglot": ("backend.benchmarks.aider_polyglot", "AiderPolyglotBenchmark"),
    "MMMU-Pro": ("backend.benchmarks.mmmu_pro", "MMMUProBenchmark"),
    "LiveBench": ("backend.benchmarks.livebench", "LiveBenchBenchmark"),
    "LiveCodeBench": ("backend.benchmarks.livecodebench", "LiveCodeBenchBenchmark"),
    "BenchMax Personal": ("backend.benchmarks.personal", "BenchMaxPersonalBenchmark"),
    "BenchMax Lite": ("backend.benchmarks.lite", "BenchMaxLiteBenchmark"),
    "BenchMax Code": ("backend.benchmarks.code_bench", "BenchMaxCodeBenchmark"),
    "BenchMax Reason": ("backend.benchmarks.reason_bench", "BenchMaxReasonBenchmark"),
    "Writing Speed Test": ("backend.benchmarks.speed_test", "WritingSpeedTestBenchmark"),
    "Coding Speed Test": ("backend.benchmarks.speed_test", "CodingSpeedTestBenchmark"),
    "BenchMax Tectonic": ("backend.benchmarks.tectonic", "BenchMaxTectonicBenchmark"),
    "TruthfulQA": ("backend.benchmarks.truthfulqa", "TruthfulQABenchmark"),
    "HellaSWAG": ("backend.benchmarks.hellaswag", "HellaSWAGBenchmark"),
    "WinoGrande": ("backend.benchmarks.winogrande", "WinoGrandeBenchmark"),
    "ARC-Challenge": ("backend.benchmarks.arc", "ARCBenchmark"),
    "CommonSenseQA": ("backend.benchmarks.commonsenseqa", "CommonSenseQABenchmark"),
    "Long Context Memory": ("backend.benchmarks.long_context_memory", "LongContextMemoryBenchmark"),
    "NIAHS": ("backend.benchmarks.niahs", "NIAHSBenchmark"),
    "GAIA": ("backend.benchmarks.gaia", "GAIABenchmark"),
    "Tau3-Airline": ("backend.benchmarks.taubench_airline", "Tau3AirlineBenchmark"),
    "BenchMax ToolCall": ("backend.benchmarks.toolcall", "BenchMaxToolCallBenchmark"),
}


def _instantiate_benchmark(benchmark_name: str, db, client, quick_test=False, hard=False):
    entry = BENCHMARK_CLASSES.get(benchmark_name)
    if not entry:
        raise ValueError(f"Unknown benchmark: {benchmark_name}")
    mod_path, cls_name = entry
    mod = __import__(mod_path, fromlist=[cls_name])
    cls = getattr(mod, cls_name)
    kwargs = {}
    if "hard" in benchmark_name.lower():
        kwargs["hard"] = True
    return cls(db, client, quick_test=quick_test, **kwargs)


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
                if quick_test is None:
                    quick_test = params.get("quick_test", False)
                if temp is not None:
                    params.setdefault("temperature", temp)
                elif "temperature" in params:
                    del params["temperature"]
                params.setdefault("max_completion_tokens", max_tokens)
                params.setdefault("system_prompt", sys_prompt)
                params.setdefault("api_key", api_key)
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

    thread = threading.Thread(target=_run, daemon=True)
    with _active_threads_lock:
        existing = _active_threads.get(run_id)
        if existing and existing.is_alive():
            logger.warning(f"Run {run_id} already has an active thread — skipping duplicate start.")
            return None
        _active_threads[run_id] = thread
    thread.start()
    return thread



def _chain_batch(remaining_ids, api_url, api_key, temp, max_tokens, sys_prompt, quick_test, context_length=None):
    """When a batch run completes, finds the next PENDING run via _remaining_ids, resets halt_ev, and triggers it. Guarded by _batch_lock for _active_batch_id."""
    global _active_batch_id, _batch_start_time
    if not remaining_ids:
        # Batch fully chained — clear the active-batch marker so the UI
        # doesn't keep showing a stale "Batch N/N" card forever.
        with _batch_lock:
            _active_batch_id = None
            _batch_start_time = None
        return
    with _active_threads_lock:
        live = {rid for rid, t in _active_threads.items() if t.is_alive()}
    remaining_ids = [rid for rid in remaining_ids if rid not in live]
    if not remaining_ids:
        with _batch_lock:
            _active_batch_id = None
            _batch_start_time = None
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


def _build_batch_summary(batch_id: str) -> pd.DataFrame:
    with get_db() as db:
        runs = db.query(Run).options(
            joinedload(Run.results).load_only(
                Result.correct, Result.tps, Result.ttft,
                Result.thinking_tokens, Result.response_tokens,
            )
        ).filter(Run.batch_id == batch_id).order_by(Run.id).all()
        rows = []
        for r in runs:
            results = r.results
            n = len(results)
            stats = _compute_result_stats(results)
            rows.append({
                "Run ID": r.id,
                "Benchmark": r.benchmark_name,
                "Status": r.status,
                "Correct": stats["correct"],
                "Total": stats["total"],
                "Accuracy": f"{stats['accuracy']}%" if stats["total"] else "0%",
                "Avg TPS": stats["avg_tps"],
                "Avg TTFT": f"{stats['avg_ttft']}s" if stats["ttft_vals"] else "0s",
                "Total Tokens": stats["total_tk"],
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()


def _build_histogram(results, value_key: str, label: str, bins: int = 15, precision: int = 2) -> pd.DataFrame:
    """Build a histogram DataFrame for a given metric (tps or ttft)."""
    stats = _compute_result_stats(results)
    vals = stats[value_key]
    if not vals:
        return pd.DataFrame()
    if len(set(vals)) <= 1:
        val = vals[0]
        return pd.DataFrame({label: [f"{round(val, precision)}"], "Count": [len(vals)]})
    counts, edges = pd.cut(pd.Series(vals), bins=bins, retbins=True, precision=precision)
    bin_labels = [f"{round(edges[i], precision)}-{round(edges[i+1], precision)}" for i in range(len(edges) - 1)]
    return pd.DataFrame({label: bin_labels, "Count": counts.value_counts(sort=False).values})


def _build_tps_histogram(results, bins=15) -> pd.DataFrame:
    return _build_histogram(results, "tps_vals", "TPS Range", bins=bins, precision=1)


def _build_ttft_histogram(results, bins=15) -> pd.DataFrame:
    return _build_histogram(results, "ttft_vals", "TTFT Range (s)", bins=bins, precision=3)


def _build_aggregated_token_chart(results) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Sample": r.task_id,
            "Thinking": r.thinking_tokens or 0,
            "Response": r.response_tokens or 0,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _build_per_category_chart(results, benchmark_name="", backfill=None) -> pd.DataFrame:
    rows = []
    for r in results:
        extra = {}
        if r.scoring_details:
            try:
                extra = json.loads(r.scoring_details)
            except (json.JSONDecodeError, TypeError):
                logger.debug("Malformed scoring_details for result %s", r.id)
        cat = extra.get("category")
        if not cat and backfill:
            cat = backfill.get(r.task_id)
        if not cat:
            cat = r.task_id.split("/")[0] if "/" in r.task_id else benchmark_name
        rows.append({"Category": cat, "Correct": 1 if r.correct else 0, "Total": 1})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    grouped = df.groupby("Category", sort=True).agg({"Correct": "sum", "Total": "sum"}).reset_index()
    grouped["Accuracy"] = (grouped["Correct"] / grouped["Total"] * 100).round(1)
    grouped = grouped.sort_values("Category", key=lambda s: s.str.lower()).reset_index(drop=True)
    return grouped


def _build_batch_latency_chart(runs) -> pd.DataFrame:
    rows = []
    for r in runs:
        results = r.results
        stats = _compute_result_stats(results)
        rows.append({
            "Benchmark": r.benchmark_name,
            "Avg TPS": stats["avg_tps"],
            "Avg TTFT (s)": stats["avg_ttft"],
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


_dataset_scan_cache: pd.DataFrame | None = None
_dataset_scan_cache_time: float = 0.0
_DATASET_SCAN_CACHE_TTL = 30.0  # seconds


def _dataset_files(rel_path) -> list:
    """Normalize a DATASETS path entry (str or list of str) into a list of paths."""
    if isinstance(rel_path, (list, tuple)):
        return list(rel_path)
    return [rel_path]


def check_benchmark_readiness(benchmark_name: str, quick_test: bool = False) -> List[dict]:
    """Return a list of readiness issues that would prevent a benchmark from running.

    An empty list means the benchmark is ready to start. Each issue has keys:
    benchmark, kind (``dataset`` | ``runtime``), message, action
    (``install_dataset`` | ``download_runtime``).
    """
    issues: List[dict] = []

    # Datasets are only required for full runs; quick_test uses the bundled mini set.
    if not quick_test:
        entry = DATASETS.get(benchmark_name)
        if entry:
            rel_path, _ = entry
            missing = []
            for f in _dataset_files(rel_path):
                candidates = [ROOT / f, Path.cwd() / f]
                if EXE_DIR:
                    candidates.extend([EXE_DIR / f, EXE_DIR.parent / f])
                if not any(p.exists() for p in candidates):
                    missing.append(f)
            if missing:
                issues.append({
                    "benchmark": benchmark_name,
                    "kind": "dataset",
                    "message": f"The {benchmark_name} dataset is not installed (missing: {', '.join(missing)}).",
                    "action": "install_dataset",
                })

    # Aider Polyglot — Docker-only (benchmax-sandbox has all runtimes).
    if benchmark_name == "Aider Polyglot":
        from backend.config import SANDBOX_USE_DOCKER
        docker_available = SANDBOX_USE_DOCKER and _docker_daemon_running()
        if not docker_available:
            from backend.sandbox.docker_executor import _image_exists
            if not _image_exists():
                issues.append({
                    "benchmark": benchmark_name,
                    "kind": "runtime",
                    "message": "Aider Polyglot needs Docker image (click Build Docker Image).",
                    "action": "download_runtime",
                })

    return issues


def _scan_datasets() -> pd.DataFrame:
    global _dataset_scan_cache, _dataset_scan_cache_time
    now = time.time()
    if _dataset_scan_cache is not None and (now - _dataset_scan_cache_time) < _DATASET_SCAN_CACHE_TTL:
        return _dataset_scan_cache

    import json as _json
    from backend.config import BENCHMARK_META
    rows = []
    for name, (rel_path, _) in DATASETS.items():
        files = _dataset_files(rel_path)
        sample_count = "—"
        found = True
        for f in files:
            candidates = [ROOT / f, Path.cwd() / f]
            if EXE_DIR:
                candidates.extend([EXE_DIR / f, EXE_DIR.parent / f])
            file_found = any(p.exists() for p in candidates)
            if not file_found:
                found = False
                break
            # Use static count from BENCHMARK_META when available (avoids reading 500 MB files).
            if sample_count == "—" and name in BENCHMARK_META:
                sample_count = f"{BENCHMARK_META[name]['samples']:,}"
            if sample_count == "—":
                for p in candidates:
                    if p.exists():
                        try:
                            # For small/medium files just count JSON length; for huge files this fallback is skipped above.
                            data = _json.loads(p.read_text(encoding="utf-8"))
                            sample_count = str(len(data)) if isinstance(data, list) else str(len(data.keys()))
                            # Normalise with commas
                            try:
                                sample_count = f"{int(sample_count):,}"
                            except Exception:
                                pass
                        except Exception:
                            logger.warning(f"Failed to read dataset file {p}", exc_info=True)
                            sample_count = "?"
                        break
        meta = BENCHMARK_META.get(name, {})
        rows.append({
            "Benchmark": name,
            "Installed": "✅" if found else "❌",
            "Samples": sample_count if found else "—",
            "Category": meta.get("category", "—"),
            "Docker": "🐳" if meta.get("docker") else "",
            "Short": meta.get("short", ""),
        })
    result = pd.DataFrame(rows)
    _dataset_scan_cache = result
    _dataset_scan_cache_time = now
    return result


async def connect_lm_studio(api_url: str, api_key: str = "") -> tuple[str, pd.DataFrame, list, dict]:
    """Hits /v1/models (simple list) and /api/v0/models (metadata: context length) and merges them."""
    metadata = {}
    try:
        client = _make_client(api_url, api_key)
        try:
            models_raw, meta = await asyncio.gather(
                client.get_loaded_models(),
                client.get_models_metadata(),
            )
        finally:
            await client.aclose()

        if not models_raw:
            status = "Connected, but no models loaded."
            df = pd.DataFrame(columns=["id"])
            choices = []
        else:
            model_ids = [m.get("id", f"model_{i}") for i, m in enumerate(models_raw)]
            df = pd.DataFrame({"id": model_ids, "Model": model_ids})
            choices = model_ids
            status = f"Connected — {len(model_ids)} model(s) loaded."

        if meta:
            metadata = meta
            for mid in meta:
                ctx = meta[mid].get("max_context_length", "?")
                status += f"\n  {mid}: context={ctx}"
    except Exception as e:
        logger.error(f"connect_lm_studio failed: {e}", exc_info=True)
        status = f"Connection failed: {e}"
        df = pd.DataFrame(columns=["id"])
        choices = []

    return status, df, choices, metadata


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
                "yes" if _active_batch_id else "no",
            )

            _start_benchmark_thread(
                run_id, api_url, api_key, temp, max_tokens, sys_prompt,
                benchmark_name=benchmark_name, quick_test=quick_test,
                context_length=context_length,
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
                global _active_batch_id, _batch_start_time
                _active_batch_id = batch_id
                _batch_start_time = time.time()

            summary_df = _build_batch_summary(batch_id)
            first_id = run_ids[0] if run_ids else None

            _start_benchmark_thread(
                run_ids[0], api_url, api_key, temp, max_tokens, sys_prompt,
                benchmark_name=selected_benchmarks[0], quick_test=quick_test,
                _remaining_ids=run_ids[1:] if len(run_ids) > 1 else None,
                context_length=context_length,
            )
            return first_id, batch_id, f"Batch {batch_id[:8]} started — {len(run_ids)} benchmarks.", summary_df, batch_id[:8]
        except Exception as e:
            db.rollback()
            logger.error(f"start_batch failed: {e}", exc_info=True)
            return None, "", str(e), pd.DataFrame(), ""


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
    global _active_batch_id, _batch_start_time
    import httpx as _httpx

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
                        params["api_key"] = api_key
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
        was_halted = _queue_halted()
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
                _active_batch_id = None
                _batch_start_time = None
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
                _active_batch_id = None
                _batch_start_time = None
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
                            global _active_batch_id, _batch_start_time
                            _active_batch_id = run.batch_id
                            _batch_start_time = time.time()

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


def load_history(offset: int = 0, limit: int = 0) -> tuple[pd.DataFrame, int]:
    """Load run history with aggregated statistics per run.

    Returns a DataFrame with columns: Run ID, Model, Benchmark, Status, Accuracy,
    Avg TPS, Avg TTFT, Tokens, Duration, Notes, Date. Supports pagination via
    offset/limit parameters.

    Args:
        offset: Number of runs to skip (for pagination).
        limit: Maximum runs to return (0 = all).

    Returns:
        Tuple of (history_df, total_count).
    """
    with get_db() as db:
        base = db.query(Run).filter(Run.status != "PENDING").order_by(Run.id.desc())
        total = db.query(sa_func.count(Run.id)).filter(Run.status != "PENDING").scalar()
        if limit > 0:
            runs = base.offset(offset).limit(limit).all()
        else:
            runs = base.all()
        run_ids = [r.id for r in runs]
        batch_stats = _compute_batch_stats_sql(db, run_ids) if run_ids else {}
        # Precompute per-needle stats for NIAHS (5 needles × 3 samples = 15 expanded points)
        needle_stats: dict[int, tuple[int, int]] = {}
        niahs_ids = [r.id for r in runs if r.benchmark_name == "NIAHS"]
        if niahs_ids:
            try:
                niahs_results = db.query(Result).filter(Result.run_id.in_(niahs_ids)).all()
                tmp: dict[int, list[int]] = {rid: [0, 0] for rid in niahs_ids}
                for res in niahs_results:
                    sd = None
                    if res.scoring_details:
                        try:
                            sd = json.loads(res.scoring_details)
                        except Exception:
                            sd = None
                    if isinstance(sd, dict):
                        per = sd.get("per_depth_correct")
                        if isinstance(per, dict) and per:
                            tmp[res.run_id][0] += sum(1 for v in per.values() if v)
                            tmp[res.run_id][1] += len(per)
                        elif "depth" in sd:
                            tmp[res.run_id][1] += 1
                            if res.correct:
                                tmp[res.run_id][0] += 1
                for rid, (c, t) in tmp.items():
                    if t:
                        needle_stats[rid] = (c, t)
            except Exception as e:
                logger.warning(f"Failed to compute NIAHS needle stats: {e}")
        rows = []
        for r in runs:
            stats = batch_stats.get(r.id, {"total": 0, "correct": 0, "avg_tps": 0, "avg_ttft": 0, "avg_prompt_tps": 0, "total_tk": 0, "avg_tokens": 0, "accuracy": 0})
            n = stats["total"]
            ok = stats["correct"]
            total_tk = stats["total_tk"]
            avg_tokens = stats["avg_tokens"]
            duration_str = "—"
            if r.status in ("COMPLETED", "FAILED", "HALTED") and r.updated_at and r.created_at:
                diff_sec = int((r.updated_at - r.created_at).total_seconds())
                if diff_sec >= 60:
                    duration_str = f"{diff_sec // 60}m {diff_sec % 60}s"
                else:
                    duration_str = f"{diff_sec}s"
            elif r.status in ("RUNNING", "PAUSED"):
                duration_str = "In Progress"

            display_status = r.status
            if display_status == "FAILED":
                display_status = "ERROR"

            params_dict = r.get_parameters()
            ctx_len_val = params_dict.get("context_length")
            # Fallback for old NIAHS runs created before context_length was stored
            if ctx_len_val is None and r.benchmark_name == "NIAHS":
                ctx_len_val = 65536
            if ctx_len_val is not None:
                try:
                    ctx_int = int(ctx_len_val)
                    ctx_str = f"{ctx_int:,}"
                    ctx_k = f"{ctx_int // 1024}K" if ctx_int >= 1024 else str(ctx_int)
                except Exception:
                    ctx_str = str(ctx_len_val)
                    ctx_k = ctx_str
            else:
                ctx_str = "—"
                ctx_k = "—"
                ctx_len_val = None

            # NIAHS per-needle breakdown (e.g. 14/15 needles vs 2/3 strict samples)
            needle_disp = "—"
            needle_raw = ""
            if r.id in needle_stats:
                nc, nt = needle_stats[r.id]
                pct = round(nc / nt * 100, 1) if nt else 0
                needle_disp = f"{nc}/{nt} ({pct}%)"
                needle_raw = f"{nc}/{nt}"

            rows.append({
                "Run ID": r.id,
                "Model": r.model_name,
                "Benchmark": r.benchmark_name,
                "Status": display_status,
                "Progress": f"{r.current_index}/{r.total_samples}",
                "Correct": ok,
                "Total": n,
                "Accuracy": f"{round(ok/n*100, 1)}%" if n else "0%",
                "Needles": needle_disp,
                "Needles Raw": needle_raw,
                "Avg TPS": stats["avg_tps"],
                "Avg TTFT": stats["avg_ttft"],
                "Avg Prompt TPS": stats["avg_prompt_tps"],
                "Avg Tokens": avg_tokens,
                "Total Tokens": total_tk,
                "Context Length": ctx_str,
                "Context Length Raw": ctx_len_val if ctx_len_val is not None else "",
                "Context K": ctx_k,
                "Duration": duration_str,
                "Batch": r.batch_id or "",
                "Notes": r.notes or "",
                "Created": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame(), total


def load_run_details(run_id_str: str) -> tuple[str, pd.DataFrame, list, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads Run + all Results via joinedload, computes summary metrics (avg_tps, ttft, accuracy, token breakdown) and chart data (per-category, token, histograms). Accuracy = correct/total with 0-division guard."""
    with get_db() as db:
        try:
            run_id = int(run_id_str)
            run = db.query(Run).options(joinedload(Run.results)).filter(Run.id == run_id).first()
            if not run:
                return "Run not found.", pd.DataFrame(), [], pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

            results = run.results
            stats = _compute_result_stats(results)
            n = stats["total"]
            ok = stats["correct"]
            tps_vals = stats["tps_vals"]
            ttft_vals = stats["ttft_vals"]
            total_tk = stats["total_tk"]
            think_tk = stats["think_tk"]
            resp_tk = stats["resp_tk"]

            params_dict = run.get_parameters()
            quick_test = params_dict.get("quick_test", False)
            ctx_len_val = params_dict.get("context_length")
            if ctx_len_val is None and run.benchmark_name == "NIAHS":
                # legacy fallback
                ctx_len_val = 65536
            ctx_line = ""
            if ctx_len_val is not None:
                try:
                    ctx_int = int(ctx_len_val)
                    ctx_line = f"Context Length: `{ctx_int:,} tokens ({ctx_int // 1024}K)`  \n"
                except Exception:
                    ctx_line = f"Context Length: `{ctx_len_val}`  \n"
            elif run.benchmark_name == "NIAHS":
                ctx_line = f"Context Length: `65,536 tokens (64K)`  \n"

            # For NIAHS, compute per-needle (expanded 5×3=15) accuracy in addition to strict sample accuracy.
            needle_line = ""
            if run.benchmark_name == "NIAHS" and results:
                total_needles = 0
                correct_needles = 0
                for res in results:
                    sd = None
                    if res.scoring_details:
                        try:
                            sd = json.loads(res.scoring_details)
                        except Exception:
                            sd = None
                    if isinstance(sd, dict):
                        per = sd.get("per_depth_correct")
                        if isinstance(per, dict) and per:
                            total_needles += len(per)
                            correct_needles += sum(1 for v in per.values() if v)
                        elif "depth" in sd:
                            # legacy single-needle
                            total_needles += 1
                            if res.correct:
                                correct_needles += 1
                if total_needles:
                    per_needle_pct = round(correct_needles / total_needles * 100, 1)
                    needle_line = f"Needle Accuracy: `{correct_needles}/{total_needles} ({per_needle_pct}%)` — strict `{ok}/{n} samples ({round(ok/n*100, 1) if n else 0}%)`  \n"
                    # Also enrich history stats: if user misses 1 of 5 in 1 of 3 samples,
                    # strict = 2/3 (66.7%), needle = 14/15 (93.3%). Both shown.

            summary_md = (
                f"**Run {run.id} — {run.benchmark_name}  \n"
                f"Model: `{run.model_name}`  \n"
                f"Status: **{run.status}**  |  "
                f"Accuracy: **{ok}/{n} ({round(ok/n*100, 1) if n else 0}%)**  \n"
                f"{ctx_line}"
                f"{needle_line}"
                f"Avg TPS: `{round(sum(tps_vals)/len(tps_vals), 1) if tps_vals else 0}`  |  "
                f"Avg TTFT: `{round(sum(ttft_vals)/len(ttft_vals), 3) if ttft_vals else 0}s`  \n"
                f"Total Tokens: {total_tk}  "
                f"(Thinking: {round(think_tk / (think_tk + resp_tk) * 100, 1) if (think_tk + resp_tk) else 0}%, "
                f"Response: {round(resp_tk / (think_tk + resp_tk) * 100, 1) if (think_tk + resp_tk) else 0}%)  \n"
                f"Created: {run.created_at.strftime('%Y-%m-%d %H:%M:%S') if run.created_at else 'N/A'}"
            )

            rows = []
            failed_tasks = []
            # Old runs predate per-question category tracking — backfill from
            # the dataset so charts/table group correctly (e.g. LiveCodeBench
            # easy/medium/hard). Skipped when every result already has one.
            cat_backfill: dict[str, str] = {}
            try:
                if any(_stored_result_category(r) is None for r in results):
                    cat_backfill = _backfill_category_map(
                        run.benchmark_name, db, [r.task_id for r in results]
                    )
            except Exception:
                logger.debug("Category backfill failed for run %s", run.id, exc_info=True)
            for r in results:
                row = {
                    "ID": r.id,
                    "Task": r.task_id,
                    "Correct": "✅" if r.correct else "❌",
                    "TPS": round(r.tps, 1) if r.tps else 0,
                    "TTFT (s)": round(r.ttft, 3) if r.ttft else 0,
                    "Tokens": (r.thinking_tokens or 0) + (r.response_tokens or 0),
                    "Thinking": r.thinking_tokens or 0,
                    "Response": r.response_tokens or 0,
                    "Error": (r.error_message or "")[:80] if r.error_message else "",
                }
                row = _add_scoring_columns(row, r)
                if "category" not in row and r.task_id in cat_backfill:
                    row["category"] = cat_backfill[r.task_id]
                rows.append(row)
                if not r.correct and r.task_id != "personal_bms_score" and r.task_id != "lite_bms_score":
                    failed_tasks.append(r.task_id)

            samples_df = pd.DataFrame(rows) if rows else pd.DataFrame()
            token_df = _build_aggregated_token_chart(results)
            ttft_hist = _build_ttft_histogram(results)
            tps_hist = _build_tps_histogram(results)
            cat_chart = _build_per_category_chart(results, run.benchmark_name, backfill=cat_backfill)

            return summary_md, samples_df, failed_tasks, token_df, ttft_hist, tps_hist, cat_chart
        except Exception as e:
            logger.error(f"load_run_details error: {e}", exc_info=True)
            return f"Error: {e}", pd.DataFrame(), [], pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def load_batch_summary(batch_id_str: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load aggregated results for a batch of runs.

    Args:
        batch_id_str: The batch UUID string.

    Returns:
        Tuple of (summary_df, chart_df, latency_chart_df) — summary per benchmark,
        accuracy chart data, and latency/token chart data.
    """
    with get_db() as db:
        runs = db.query(Run).options(
            joinedload(Run.results).load_only(
                Result.correct, Result.tps, Result.ttft,
                Result.thinking_tokens, Result.response_tokens,
            )
        ).filter(Run.batch_id == batch_id_str).order_by(Run.id).all()
        summary_rows = []
        chart_rows = []
        for r in runs:
            results = r.results
            stats = _compute_result_stats(results)
            summary_rows.append({
                "Run ID": r.id,
                "Benchmark": r.benchmark_name,
                "Status": r.status,
                "Correct": stats["correct"],
                "Total": stats["total"],
                "Accuracy": f"{stats['accuracy']}%" if stats["total"] else "0%",
                "Avg TPS": stats["avg_tps"],
                "Avg TTFT": f"{stats['avg_ttft']}s" if stats["ttft_vals"] else "0s",
                "Total Tokens": stats["total_tk"],
            })
            chart_rows.append({
                "Benchmark": r.benchmark_name,
                "Status": r.status,
            })
        summary_df = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame()
        chart_df = pd.DataFrame(chart_rows) if chart_rows else pd.DataFrame()
        latency_df = _build_batch_latency_chart(runs)
    return summary_df, chart_df, latency_df



def load_leaderboard() -> pd.DataFrame:
    """Load the local leaderboard (completed runs with aggregated metrics).

    Returns:
        DataFrame with columns: run_id, model_name, benchmark, accuracy, avg_tps,
        avg_ttft, total_tokens, samples, date, notes.
    """
    with get_db() as db:
        runs = db.query(Run).filter(
            Run.status.in_(["COMPLETED", "FAILED"])
        ).order_by(Run.id.desc()).limit(500).all()
        run_ids = [r.id for r in runs]
        batch_stats = _compute_batch_stats_sql(db, run_ids) if run_ids else {}
        # Per-needle stats for NIAHS leaderboard
        needle_stats: dict[int, tuple[int, int]] = {}
        niahs_ids = [r.id for r in runs if r.benchmark_name == "NIAHS"]
        if niahs_ids:
            try:
                niahs_results = db.query(Result).filter(Result.run_id.in_(niahs_ids)).all()
                tmp: dict[int, list[int]] = {rid: [0, 0] for rid in niahs_ids}
                for res in niahs_results:
                    sd = None
                    if res.scoring_details:
                        try:
                            sd = json.loads(res.scoring_details)
                        except Exception:
                            sd = None
                    if isinstance(sd, dict):
                        per = sd.get("per_depth_correct")
                        if isinstance(per, dict) and per:
                            tmp[res.run_id][0] += sum(1 for v in per.values() if v)
                            tmp[res.run_id][1] += len(per)
                        elif "depth" in sd:
                            tmp[res.run_id][1] += 1
                            if res.correct:
                                tmp[res.run_id][0] += 1
                for rid, (c, t) in tmp.items():
                    if t:
                        needle_stats[rid] = (c, t)
            except Exception as e:
                logger.warning(f"Failed to compute NIAHS needle stats (leaderboard): {e}")
        rows = []
        for r in runs:
            stats = batch_stats.get(r.id, {"total": 0, "correct": 0, "avg_tps": 0, "avg_ttft": 0, "avg_prompt_tps": 0, "total_tk": 0, "accuracy": 0})
            n = stats["total"]
            ok = stats["correct"]
            accuracy = stats["accuracy"]
            avg_tps = stats["avg_tps"]
            avg_ttft = stats["avg_ttft"]
            avg_prompt_tps = stats["avg_prompt_tps"]
            total_tk = stats["total_tk"]
            params = r.get_parameters()
            quick_test = params.get("quick_test")
            if quick_test is None:
                quick_test = (r.total_samples or 0) <= 10
            ctx_len_val = params.get("context_length")
            if ctx_len_val is None and r.benchmark_name == "NIAHS":
                ctx_len_val = 65536
            if ctx_len_val is not None:
                try:
                    ctx_int = int(ctx_len_val)
                    ctx_str = f"{ctx_int:,}"
                    ctx_k = f"{ctx_int // 1024}K" if ctx_int >= 1024 else str(ctx_int)
                except Exception:
                    ctx_str = str(ctx_len_val)
                    ctx_k = ctx_str
            else:
                ctx_str = "—"
                ctx_k = "—"
                ctx_len_val = None
            needle_disp = "—"
            if r.id in needle_stats:
                nc, nt = needle_stats[r.id]
                pct = round(nc / nt * 100, 1) if nt else 0
                needle_disp = f"{nc}/{nt} ({pct}%)"
            rows.append({
                "Run ID": r.id,
                "Model": r.model_name,
                "Benchmark": r.benchmark_name,
                "Accuracy": f"{accuracy}%",
                "Needles": needle_disp,
                "Avg TPS": avg_tps,
                "Avg TTFT": avg_ttft,
                "Avg Prompt TPS": avg_prompt_tps,
                "Passed": f"{ok}/{n}",
                "Tokens": total_tk,
                "Context Length": ctx_str,
                "Context Length Raw": ctx_len_val if ctx_len_val is not None else "",
                "Context K": ctx_k,
                "Date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                "status": r.status,
                "QuickTest": quick_test,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()


def delete_leaderboard_entry(run_id_str: str) -> tuple[pd.DataFrame, str]:
    """Delete a single leaderboard entry by run ID.

    Args:
        run_id_str: The run ID as a string.

    Returns:
        Tuple of (updated_leaderboard_df, status_message).
    """
    with get_db() as db:
        try:
            run_id = int(run_id_str)
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                return load_leaderboard(), "Run not found."
            db.delete(run)
            db.commit()
            return load_leaderboard(), f"Run {run_id} deleted."
        except Exception as e:
            logger.error(f"delete_leaderboard_entry failed: {e}", exc_info=True)
            return pd.DataFrame(), str(e)


def clear_all_history(confirm_text: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Clear all run history and leaderboard entries.

    Args:
        confirm_text: Must be exactly "CONFIRM" to proceed.

    Returns:
        Tuple of (history_df, leaderboard_df, status_message).
    """
    if confirm_text != "CONFIRM":
        h, _ = load_history()
        lb = load_leaderboard()
        return h, lb, "Type CONFIRM to clear all history."

    with get_db() as db:
        try:
            db.query(Result).delete()
            db.query(Run).delete()
            db.commit()
            # In-memory run state so the next poll doesn't re-serve
            # deleted data or reference stale halt events.
            with _halt_events_lock:
                _halt_events.clear()
            with _active_threads_lock:
                _active_threads.clear()
            h = pd.DataFrame()
            lb = pd.DataFrame()
            return h, lb, "All history cleared."
        except Exception as e:
            return load_history()[0], load_leaderboard(), str(e)


def load_cross_comparison(run_ids_csv: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load cross-run comparison data for the selected runs.

    Args:
        run_ids_csv: Comma-separated run IDs (e.g. "1,2,3").

    Returns:
        Tuple of (accuracy_df, latency_df, tokens_df) — comparison data across runs.
    """
    if not run_ids_csv:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    ids = [int(x.strip()) for x in run_ids_csv.split(",") if x.strip().isdigit()]
    if not ids:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    with get_db() as db:
        acc_rows = []
        lat_rows = []
        tok_rows = []
        runs = db.query(Run).options(joinedload(Run.results)).filter(Run.id.in_(ids)).all()
        for run in runs:
            results = run.results
            stats = _compute_result_stats(results)
            n = stats["total"]
            ok = stats["correct"]
            total_tk = stats["total_tk"]
            label = f"#{run.id} {run.benchmark_name}"
            acc_rows.append({
                "Run": label,
                "Accuracy": stats["accuracy"],
                "Correct": ok,
                "Total": n,
            })
            lat_rows.append({
                "Run": label,
                "Avg TPS": stats["avg_tps"],
                "Avg TTFT (s)": stats["avg_ttft"],
            })
            tok_rows.append({
                "Run": label,
                "Thinking": stats["think_tk"],
                "Response": stats["resp_tk"],
                "Total": total_tk,
            })
        return (
            pd.DataFrame(acc_rows) if acc_rows else pd.DataFrame(),
            pd.DataFrame(lat_rows) if lat_rows else pd.DataFrame(),
            pd.DataFrame(tok_rows) if tok_rows else pd.DataFrame(),
        )


# ── Export ────────────────────────────────────────────────────────────

def _export_dataframe(df: pd.DataFrame, prefix: str, fmt: str) -> tuple[str | None, str]:
    os.makedirs(ROOT / "records", exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    if fmt == "CSV":
        path = ROOT / "records" / f"{prefix}_{ts}.csv"
        df.to_csv(path, index=False)
        return str(path), f"Exported to {path.name}"
    elif fmt == "JSON":
        path = ROOT / "records" / f"{prefix}_{ts}.json"
        df.to_json(path, orient="records", indent=2)
        return str(path), f"Exported to {path.name}"
    elif fmt == "XLSX":
        path = ROOT / "records" / f"{prefix}_{ts}.xlsx"
        df.to_excel(path, index=False, engine="openpyxl")
        return str(path), f"Exported to {path.name}"
    return None, f"Unsupported format: {fmt}"


def export_results(run_id_str: str, format_type: str) -> tuple[str | None, str]:
    """Exports a single run's results as CSV or JSON. Includes per-sample correctness, timing, tokens, and errors."""
    with get_db() as db:
        run_id = int(run_id_str)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return None, "Run not found."
        results = db.query(Result).filter(Result.run_id == run_id).order_by(Result.id).all()
        rows = [_result_to_export_dict(r) for r in results]
        if not rows:
            return None, "No results to export."
        df = pd.DataFrame(rows)
        return _export_dataframe(df, f"run_{run_id}", format_type)


def export_batch_results(batch_id: str, format_type: str) -> tuple[str | None, str]:
    """Exports all results across a batch as CSV or JSON. Same fields as export_results but aggregated by run within the batch."""
    with get_db() as db:
        runs = db.query(Run).filter(Run.batch_id == batch_id).order_by(Run.id).all()
        if not runs:
            return None, "Batch not found."
        results = db.query(Result).filter(
            Result.run_id.in_([r.id for r in runs])
        ).order_by(Result.run_id, Result.id).all()
        rows = [_result_to_export_dict(r) for r in results]
        if not rows:
            return None, "No results to export."
        df = pd.DataFrame(rows)
        return _export_dataframe(df, f"batch_{batch_id[:8]}", format_type)


def export_all_history(format_type: str = "CSV") -> tuple[str | None, str]:
    """Exports all completed/failed runs as CSV or JSON via load_history(). Includes per-run summary metrics."""
    df, _ = load_history()
    return _export_dataframe(df, "all_history", format_type)


def export_leaderboard(format_type: str = "CSV") -> tuple[str | None, str]:
    """Exports the leaderboard as CSV, JSON, or Excel."""
    df = load_leaderboard()
    if df.empty:
        return None, "No leaderboard data to export."
    return _export_dataframe(df, "leaderboard", format_type)


def export_comparison(run_ids_csv: str, format_type: str = "CSV") -> tuple[str | None, str]:
    """Exports cross-run comparison (accuracy, latency, tokens) as CSV, JSON, or Excel."""
    acc_df, lat_df, tok_df = load_cross_comparison(run_ids_csv)
    if acc_df.empty:
        return None, "No comparison data to export."
    merged = acc_df.merge(lat_df, on="Run", how="outer").merge(tok_df, on="Run", how="outer")
    return _export_dataframe(merged, "comparison", format_type)


def export_run_markdown(run_id_str: str) -> tuple[str | None, str]:
    """Generates a Markdown report for a single run."""
    with get_db() as db:
        run_id = int(run_id_str)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return None, "Run not found."
        results = db.query(Result).filter(Result.run_id == run_id).order_by(Result.id).all()
        stats = _compute_result_stats(results)
        n = stats["total"]
        ok = stats["correct"]
        accuracy = stats["accuracy"]

        duration_str = "—"
        if run.status in ("COMPLETED", "FAILED", "HALTED") and run.updated_at and run.created_at:
            diff_sec = int((run.updated_at - run.created_at).total_seconds())
            if diff_sec >= 3600:
                duration_str = f"{diff_sec // 3600}h {(diff_sec % 3600) // 60}m"
            elif diff_sec >= 60:
                duration_str = f"{diff_sec // 60}m {diff_sec % 60}s"
            else:
                duration_str = f"{diff_sec}s"

        failed = [r for r in results if not r.correct]
        errors = [r for r in results if r.error_message]

        lines = [
            f"# BenchMax Report — {run.benchmark_name}",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Model | `{run.model_name}` |",
            f"| Benchmark | {run.benchmark_name} |",
            f"| Status | {run.status} |",
            f"| Accuracy | **{accuracy}%** ({ok}/{n}) |",
            f"| Avg TPS | {stats['avg_tps']} |",
            f"| Avg TTFT | {stats['avg_ttft']}s |",
            f"| Avg Prompt TPS | {stats['avg_prompt_tps']} |",
            f"| Total Tokens | {stats['total_tk']:,} |",
            f"| Thinking Tokens | {stats['think_tk']:,} |",
            f"| Response Tokens | {stats['resp_tk']:,} |",
            f"| Duration | {duration_str} |",
            f"| Run ID | #{run.id} |",
            f"| Date | {run.created_at.strftime('%Y-%m-%d %H:%M') if run.created_at else '—'} |",
            "",
        ]

        if failed:
            lines.append(f"## Failed Samples ({len(failed)})")
            lines.append("")
            for r in failed[:20]:
                task = r.task_id or "unknown"
                err = (r.error_message or "unknown error")[:120]
                lines.append(f"- **{task}**: {err}")
            if len(failed) > 20:
                lines.append(f"- ... and {len(failed) - 20} more")
            lines.append("")

        if errors and len(errors) != len(failed):
            err_only = [r for r in errors if r.correct]
            if err_only:
                lines.append(f"## Errors (correct but with warnings) ({len(err_only)})")
                lines.append("")
                for r in err_only[:10]:
                    lines.append(f"- **{r.task_id}**: {(r.error_message or '')[:120]}")
                lines.append("")

        if run.notes:
            lines.append(f"## Notes")
            lines.append("")
            lines.append(run.notes)
            lines.append("")

        lines.append(f"---")
        lines.append(f"*Generated by BenchMax*")

        md_content = "\n".join(lines)
        os.makedirs(ROOT / "records", exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = ROOT / "records" / f"run_{run_id}_{ts}.md"
        path.write_text(md_content, encoding="utf-8")
        return str(path), f"Exported to {path.name}"


def export_all_history_markdown() -> tuple[str | None, str]:
    """Generates a Markdown summary table of all runs."""
    df, _ = load_history()
    if df.empty:
        return None, "No history to export."

    lines = [
        "# BenchMax — All Runs Summary",
        "",
        f"*Generated {time.strftime('%Y-%m-%d %H:%M')}*",
        "",
        f"**{len(df)} runs total**",
        "",
        "| Run ID | Model | Benchmark | Status | Accuracy | Avg TPS | Avg TTFT | Tokens | Date |",
        "|--------|-------|-----------|--------|----------|---------|----------|--------|------|",
    ]

    for _, row in df.iterrows():
        rid = row.get("Run ID", "")
        model = row.get("Model", "")
        bench = row.get("Benchmark", "")
        status = row.get("Status", "")
        acc = row.get("Accuracy", "")
        tps = row.get("Avg TPS", "")
        ttft = row.get("Avg TTFT", "")
        tokens = row.get("Total Tokens", "")
        date = row.get("Created", "")
        notes = row.get("Notes", "")
        note_marker = " *" + notes + "*" if notes else ""
        lines.append(f"| {rid} | {model} | {bench} | {status} | {acc} | {tps} | {ttft} | {tokens} | {date} |{note_marker}")

    lines.extend(["", "---", "*Generated by BenchMax*"])

    md_content = "\n".join(lines)
    os.makedirs(ROOT / "records", exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = ROOT / "records" / f"all_history_{ts}.md"
    path.write_text(md_content, encoding="utf-8")
    return str(path), f"Exported to {path.name}"


def generate_diff(run_id_str: str, task_id: str) -> str:
    """Generate a side-by-side HTML diff between the expected answer and model output.

    Loads the benchmark dataset to find the ground-truth answer, fetches the
    model's response from the Result row, and produces a unified diff using
    ``difflib.HtmlDiff``. Works for all benchmark types (code, MCQ, text).
    """
    with get_db() as db:
        try:
            run_id = int(run_id_str)
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                return "<p>Run not found.</p>"
            result = db.query(Result).filter(
                Result.run_id == run_id, Result.task_id == task_id
            ).first()
            if not result:
                safe_task_id = html_mod.escape(task_id)
                return f"<p>Result for {safe_task_id} not found.</p>"
            result_data = {
                "extracted_code": result.extracted_code or "",
                "raw_response": result.raw_response or "",
                "prompt": result.prompt or "",
            }
            try:
                bench = _instantiate_benchmark(run.benchmark_name, db, None)
            except ValueError:
                # Removed/renamed benchmark (e.g. MCP-Bench, Speed Test):
                # class and dataset are gone, but old Result rows remain.
                # Fall back to stored model output instead of
                # "Error: Unknown benchmark: ...".
                safe_bench = html_mod.escape(run.benchmark_name)
                prompt = html_mod.escape((result.prompt or "")[:2000])
                extracted = html_mod.escape((result.extracted_code or "")[:2000])
                raw = html_mod.escape((result.raw_response or "")[:4000])
                return (
                    '<div style="font-family:system-ui,sans-serif;padding:16px;border-radius:8px;'
                    'background:#1e293b;border:1px solid #334155">'
                    f'<div style="color:#94a3b8;font-size:13px;margin-bottom:12px">'
                    f'Benchmark <b>{safe_bench}</b> is no longer available (removed or renamed) — '
                    'showing stored model output without expected answer.</div>'
                    f'<div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Prompt</div>'
                    f'<pre style="padding:10px;background:#0f172a;color:#94a3b8;border-radius:6px;'
                    'font-size:11px;white-space:pre-wrap;word-break:break-word;max-height:200px;overflow:auto;margin-bottom:12px">'
                    f'{prompt}</pre>'
                    f'<div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Model Answer</div>'
                    f'<pre style="padding:10px;background:#0f172a;color:#e2e8f0;border-radius:6px;'
                    'font-size:12px;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto">'
                    f'{extracted or raw}</pre>'
                    '</div>'
                )
            try:
                dataset = bench.load_dataset()
            except Exception:
                # Dataset file gone (e.g. old NIAHS single-needle stubs after
                # redesign) — still show stored question + model answer.
                logger.warning("generate_diff: dataset unavailable for %s, using stored output",
                               run.benchmark_name)
                return bench._generate_question_answer_diff({}, result_data)
            sample = next((s for s in dataset if s.get("task_id") == task_id), None)
            if not sample:
                m = re.match(r"sample_(\d+)", task_id)
                if m:
                    idx = int(m.group(1))
                    if 0 <= idx < len(dataset):
                        sample = dataset[idx]
                # Also try question_id (LiveCodeBench) and key (IFEval) lookups.
                if not sample:
                    sample = next(
                        (s for s in dataset
                         if s.get("question_id") == task_id or s.get("key") == task_id),
                        None,
                    )
                if not sample:
                    # Stale task_id (dataset regenerated since the run, e.g.
                    # NIAHS redesign, brutal rewrites) — show stored output.
                    logger.warning("generate_diff: dataset record %s not found for %s, using stored output",
                                   task_id, run.benchmark_name)
                    return bench._generate_question_answer_diff({}, result_data)
            html = bench.generate_diff(sample, result_data)
            return html
        except Exception as e:
            logger.error(f"generate_diff error: {e}", exc_info=True)
            safe_err = html_mod.escape(str(e))
            return f"<p>Error: {safe_err}</p>"


async def install_dataset(bench_name: str, hf_token: str = "") -> str:
    """Install a single benchmark dataset by running its fetch script.

    Args:
        bench_name: Benchmark name (e.g. "HumanEval", "MMLU-Pro").
        hf_token: Optional HuggingFace token for gated datasets.

    Returns:
        str: Status message with success/error details.
    """
    entry = DATASETS.get(bench_name)
    if not entry:
        return f"No dataset entry for {bench_name}."
    _, script_rel = entry
    if not script_rel:
        return f"{bench_name} does not require installation (bundled)."
    script = ROOT / script_rel
    if not script.exists():
        return f"Fetch script not found: {script}"

    env = os.environ.copy()
    if hf_token:
        env["HF_TOKEN"] = hf_token
    else:
        saved_token = _load_hf_token()
        if saved_token:
            env["HF_TOKEN"] = saved_token

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=120, env=env,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode == 0:
            global _dataset_scan_cache, _dataset_scan_cache_time
            _dataset_scan_cache = None
            return f"{bench_name} installed successfully."
        else:
            return f"Installation failed:\n{output[:500]}"
    except subprocess.TimeoutExpired:
        return f"Installation timed out for {bench_name}."
    except Exception as e:
        return f"Error: {e}"


async def install_all_missing(hf_token: str = "") -> str:
    """Install all benchmark datasets that are not yet present on disk.

    Args:
        hf_token: Optional HuggingFace token for gated datasets.

    Returns:
        str: Summary of which datasets were installed/skipped/failed.
    """
    results = []
    for name in BENCH_NAMES:
        entry = DATASETS.get(name)
        if not entry:
            continue
        rel_path, script_rel = entry
        files = _dataset_files(rel_path)
        found = True
        for f in files:
            candidates = [ROOT / f, Path.cwd() / f]
            if EXE_DIR:
                candidates.extend([EXE_DIR / f, EXE_DIR.parent / f])
            if not any(p.exists() for p in candidates):
                found = False
                break
        if found:
            continue
        status = await install_dataset(name, hf_token)
        results.append(f"{name}: {status}")
    global _dataset_scan_cache, _dataset_scan_cache_time
    _dataset_scan_cache = None
    return "\n".join(results) if results else "All datasets already installed."


async def build_docker_image() -> str:
    """Build the benchmax-sandbox Docker image with all runtimes.

    Returns:
        str: Status message with success/error details.
    """
    from backend.sandbox.docker_executor import build_image, _docker_available, _image_exists

    if not _docker_available():
        return "Docker is not available or not running. Install Docker Desktop and try again."

    if _image_exists():
        return "Docker image already built. Ready to run benchmarks."

    # Run build in thread to avoid blocking the event loop
    result = await asyncio.to_thread(build_image)
    if result["success"]:
        return "Docker image built successfully. All runtimes ready."
    else:
        return f"Docker build failed: {result.get('error', 'unknown error')}"


async def get_docker_status() -> dict:
    """Check Docker availability and image status.

    Returns:
        dict with keys: available (bool), image_exists (bool), message (str).
    """
    from backend.sandbox.docker_executor import _docker_available, _image_exists

    available = _docker_available()
    if not available:
        return {"available": False, "image_exists": False,
                "message": "Docker is not installed or not running."}

    exists = _image_exists()
    if exists:
        return {"available": True, "image_exists": True,
                "message": "Docker image ready."}
    else:
        return {"available": True, "image_exists": False,
                "message": "Docker found but image not built yet. Click 'Build Image' to create it."}


HF_TOKEN_FILE = ROOT / "records" / ".hf_token"


def _load_hf_token() -> str:
    if HF_TOKEN_FILE.exists():
        try:
            return HF_TOKEN_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            logger.warning(f"Failed to read HF token file {HF_TOKEN_FILE}", exc_info=True)
    return ""


def _save_hf_token(token: str) -> str:
    try:
        os.makedirs(HF_TOKEN_FILE.parent, exist_ok=True)
        HF_TOKEN_FILE.write_text(token.strip(), encoding="utf-8")
        return "Token saved."
    except Exception as e:
        return f"Failed to save token: {e}"


LB_SETTINGS_FILE = ROOT / "records" / ".lb_settings"


def save_lb_api_key(key: str) -> str:
    """Save the Supabase API key for online leaderboard sync.

    Args:
        key: The Supabase anon/service key.

    Returns:
        str: Status message ("Saved.").
    """
    global _LB_SUPABASE_KEY
    _LB_SUPABASE_KEY = key
    try:
        os.makedirs(LB_SETTINGS_FILE.parent, exist_ok=True)
        LB_SETTINGS_FILE.write_text(key, encoding="utf-8")
        return "API key saved."
    except Exception as e:
        return f"Failed to save: {e}"


def load_lb_settings() -> str:
    """Load the saved Supabase API key from disk.

    Returns:
        str: The API key, or empty string if not configured.
    """
    global _LB_SUPABASE_KEY
    if not _LB_SUPABASE_KEY:
        if LB_SETTINGS_FILE.exists():
            try:
                _LB_SUPABASE_KEY = LB_SETTINGS_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                logger.warning(f"Failed to read leaderboard settings {LB_SETTINGS_FILE}", exc_info=True)
    return _LB_SUPABASE_KEY


async def sync_to_online_leaderboard(_trigger=0, api_key: str | None = None) -> str:
    """Sync local leaderboard entries to the online Supabase leaderboard.

    Args:
        _trigger: Unused (for Gradio event wiring).
        api_key: Optional override for the Supabase API key.

    Returns:
        str: Status message ("Synced N entries." or error).
    """
    try:
        key = api_key or load_lb_settings()
        if not key:
            return "No API key configured."
        with get_db() as db:
            runs = db.query(Run).options(joinedload(Run.results)).filter(Run.status.in_(["COMPLETED", "FAILED"])).order_by(Run.id.desc()).all()
            if not runs:
                return "No completed runs to sync."
            records = []
            for r in runs:
                results = r.results
                stats = _compute_result_stats(results)
                n = stats["total"]
                ok = stats["correct"]
                accuracy = stats["accuracy"]
                avg_tps = stats["avg_tps"]
                avg_ttft = stats["avg_ttft"]
                records.append({
                    "id": secrets.token_hex(8),
                    "benchmark_name": r.benchmark_name,
                    "model_name": r.model_name,
                    "accuracy": accuracy,
                    "samples": n,
                    "passed": ok,
                    "avg_tps": avg_tps,
                    "avg_ttft": avg_ttft,
                    "total_tokens": stats["total_tk"],
                    "timestamp": r.created_at.isoformat() if r.created_at else "",
                })
        headers = {
            "Content-Type": "application/json",
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        async with httpx.AsyncClient(timeout=30) as hclient:
            res = await hclient.post(
                _LB_API_URL,
                json=records,
                headers=headers,
            )
        if res.status_code in (200, 201):
            return f"Synced {len(records)} entries."
        else:
            return f"Sync failed ({res.status_code}): {res.text[:200]}"
    except Exception as e:
        return f"Sync error: {e}"


def poll(active_run_id: int | None = None) -> dict:
    """Returns telemetry + run_progress + batch_progress. GPU/PowerShell telemetry cached with 2s TTL; CPU/RAM always fresh. When a batch run completes and another is PENDING, fires active_run_override to show its live progress."""
    metrics, _new_smooth_cpu, _new_smooth_gpu = _update_telemetry_history()

    cpu_text = f"CPU: {metrics.get('cpu_percent', 0):.1f}%"
    ram_text = f"RAM: {metrics.get('ram_used_gb', 0):.1f}/{metrics.get('ram_total_gb', 0):.1f} GB"
    gpu_text = f"GPU: {metrics.get('gpu_name', 'N/A')} ({metrics.get('gpu_load', 0):.1f}%)"
    vram_text = f"VRAM: {metrics.get('vram_used_mb', 0):.0f}/{metrics.get('vram_total_mb', 0):.0f} MB"

    with _telemetry_lock:
        hist_slice = telemetry_history[-60:] if telemetry_history else []

    prog_val = 0.0
    status_md = ""
    active_task = ""
    avg_tps = 0.0
    avg_ttft = 0.0
    accuracy = ""
    token_stats = ""

    batch_prog_val = 0.0
    batch_status_md = ""
    batch_eta_str = ""
    batch_summary_df = pd.DataFrame()
    batch_id_val = ""
    batch_done = 0
    batch_total = 0
    batch_current_name = ""
    active_run_override = None

    with _batch_lock:
        bid = _active_batch_id
        bst = _batch_start_time

    # Use a single DB session for all queries
    with get_db() as db:
        if active_run_id:
            run = db.query(Run).filter(Run.id == active_run_id).first()
            if run:
                stats = _compute_run_stats_sql(db, active_run_id)
                rp = _compute_run_progress(run, stats=stats)
                prog_val = rp["prog_val"]
                status_md = rp["status_md"]
                active_task = rp["active_task"]
                avg_tps = rp["avg_tps"]
                avg_ttft = rp["avg_ttft"]
                accuracy = rp["accuracy"]
                token_stats = rp["token_stats"]

        if bid:
            batch_id_val = bid
            runs = db.query(Run).filter(Run.batch_id == bid).order_by(Run.id).all()
            if runs:
                batch_total = len(runs)
                batch_done = sum(1 for r in runs if r.status in ("COMPLETED", "FAILED", "HALTED"))
                batch_prog_val = batch_done / batch_total if batch_total > 0 else 0
                running_names = [r.benchmark_name for r in runs if r.status == "RUNNING"]
                batch_current_name = running_names[0] if running_names else (runs[-1].benchmark_name if runs else "")
                batch_status_md = f"Batch: {batch_done}/{batch_total} — Current: {batch_current_name}"

                if bst and batch_done > 0:
                    total_done_samples = sum(r.current_index or 0 for r in runs if r.status in ("COMPLETED", "FAILED"))
                    total_remaining = sum((r.total_samples or 1) - (r.current_index or 0) for r in runs if r.status not in ("COMPLETED", "FAILED"))
                    if total_done_samples > 0 and total_remaining > 0:
                        elapsed = time.time() - bst
                        avg = elapsed / total_done_samples
                        est = int(avg * total_remaining)
                        batch_eta_str = f"{est // 60}m{est % 60}s" if est > 60 else f"~{est}s"

                rows = []
                batch_run_ids = [r.id for r in runs]
                batch_stats = _compute_batch_stats_sql(db, batch_run_ids)
                for r in runs:
                    stats = batch_stats[r.id]
                    rows.append({
                        "Run ID": r.id,
                        "Benchmark": r.benchmark_name,
                        "Status": r.status,
                        "Correct": stats["correct"],
                        "Total": stats["total"],
                        "Accuracy": f"{stats['accuracy']}%" if stats["total"] else "0%",
                        "Avg TPS": stats["avg_tps"],
                        "Avg TTFT": f"{stats['avg_ttft']}s" if stats["ttft_vals"] else "0s",
                        "Total Tokens": stats["total_tk"],
                    })
                batch_summary_df = pd.DataFrame(rows) if rows else pd.DataFrame()

            # active_run_override: if active run is done but batch continues
            if active_run_id:
                orig_run = db.query(Run).filter(Run.id == active_run_id).first()
                if orig_run and orig_run.status in ("COMPLETED", "FAILED", "HALTED"):
                    running = db.query(Run).filter(
                        Run.batch_id == bid, Run.status == "RUNNING"
                    ).order_by(Run.id).first()
                    if running:
                        stats = _compute_run_stats_sql(db, running.id)
                        rp = _compute_run_progress(running, stats=stats)
                        prog_val = rp["prog_val"]
                        status_md = rp["status_md"]
                        active_task = rp["active_task"]
                        avg_tps = rp["avg_tps"]
                        avg_ttft = rp["avg_ttft"]
                        accuracy = rp["accuracy"]
                        token_stats = rp["token_stats"]
                        active_run_override = running.id
                    else:
                        active_run_override = None
                else:
                    active_run_override = None
            else:
                active_run_override = None

    # Live multi-turn progress (if any multi-turn benchmark is currently running)
    live_turn = None
    try:
        from backend.benchmarks.multi_turn_base import get_live_turn_state
        lt = get_live_turn_state()
        if lt and lt.get("turn") and (time.time() - lt.get("ts", 0) < 30):
            live_turn = lt
    except Exception:
        pass

    # NOTE: history/recent-runs were previously (re)loaded here on every poll
    # tick and then discarded by the API layer — a huge amount of full-text
    # Result loading per request. The frontend fetches /api/runs separately,
    # so this is intentionally removed. Poll now only serves telemetry,
    # run progress, and batch progress.

    return {
        "prog_val": prog_val, "status_md": status_md, "active_task": active_task,
        "avg_tps": avg_tps, "avg_ttft": avg_ttft, "accuracy": accuracy, "token_stats": token_stats,
        "batch_prog_val": batch_prog_val, "batch_status_md": batch_status_md,
        "batch_eta_str": batch_eta_str, "batch_summary_df": batch_summary_df,
        "batch_id_val": batch_id_val, "batch_done": batch_done, "batch_total": batch_total,
        "batch_current_name": batch_current_name, "active_run_override": active_run_override,
        "metrics": metrics,
        "live_turn": live_turn,
    }
