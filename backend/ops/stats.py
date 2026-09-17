"""Statistics, charts, run-status reads, and the poll() payload builder."""

import json
import logging
import time

import pandas as pd
from sqlalchemy import func as sa_func, cast as sa_cast, case as sa_case, Integer as sa_Integer, Float as sa_Float
from sqlalchemy.orm import joinedload

from backend.database import Run, Result, get_db
from backend.telemetry.monitor import get_system_metrics

import backend.ops.state as _state  # noqa: E402
from backend.ops.state import (  # noqa: E402
    MAX_HISTORY_LEN,
    telemetry_history,
    _EMA_ALPHA,
    _batch_lock,
    _telemetry_lock,
)

from backend.ops.bench import _instantiate_benchmark

logger = logging.getLogger(__name__)


def _update_telemetry_history() -> tuple[dict, float, float]:
    """Append a smoothed telemetry sample to the history ring buffer.

    EMA state lives in the module-level `_ema_state` dict so smoothing
    survives across API calls (the previous parameter-passing approach
    discarded the smoothed values on every call, making the EMA inert).
    """
    metrics = get_system_metrics()
    raw_cpu = metrics.get("cpu_percent", 0.0)
    raw_gpu = metrics.get("gpu_load", 0.0)
    # Single lock acquisition (threading.Lock is NOT re-entrant): the ring
    # cap is done inline rather than via append_telemetry(), which takes
    # the same lock and would deadlock here.
    with _telemetry_lock:
        prev_cpu = _state._ema_state["cpu"]
        prev_gpu = _state._ema_state["gpu"]
        smooth_cpu = prev_cpu + _EMA_ALPHA * (raw_cpu - prev_cpu) if prev_cpu else raw_cpu
        smooth_gpu = prev_gpu + _EMA_ALPHA * (raw_gpu - prev_gpu) if prev_gpu else raw_gpu
        _state._ema_state["cpu"] = smooth_cpu
        _state._ema_state["gpu"] = smooth_gpu
        telemetry_history.append({
            "timestamp": time.time(),
            "cpu_percent": smooth_cpu,
            "ram_used_gb": metrics.get("ram_used_gb", 0.0),
            "ram_total_gb": metrics.get("ram_total_gb", 0.0),
            "gpu_load": smooth_gpu,
            "vram_used_mb": metrics.get("vram_used_mb", 0.0),
            "vram_total_mb": metrics.get("vram_total_mb", 0.0),
        })
        overflow = len(telemetry_history) - MAX_HISTORY_LEN
        if overflow > 0:
            del telemetry_history[:overflow]
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
    if benchmark_name in ("BigCodeBench", "BigCodeBench-Hard"):
        return benchmark_name
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
        logger.debug("Category backfill skipped for %s (dataset unavailable)", benchmark_name, exc_info=True)
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
        logger.debug("Live progress lookup failed for run %s", run.id, exc_info=True)
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
            _n = len(results)
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


def get_run_status(run_id: int) -> dict:
    """Live status + aggregated metrics for one run (service layer).

    Extracted from the ``GET /run/{id}/status`` router handler so DB
    aggregation lives in the service layer, not the transport layer.
    Raises :class:`RunNotFoundError` when the run does not exist.
    """
    from sqlalchemy.orm import load_only as _load_only
    from backend.ops.errors import RunNotFoundError

    with get_db() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise RunNotFoundError(run_id)
        results = db.query(Result).options(
            _load_only(
                Result.correct, Result.tps, Result.ttft,
                Result.thinking_tokens, Result.response_tokens, Result.prompt_tokens,
                Result.error_message,
            )
        ).filter(Result.run_id == run_id).all()
        stats = _compute_result_stats(results)
        rep_warnings = [r.error_message or "" for r in results if "Repetition" in (r.error_message or "")]
        safety_metrics = None
        if run.benchmark_name == "UncensorBench":
            safety_metrics = run.get_parameters().get("_safety_metrics")
        return {
            "run_id": run.id,
            "model_name": run.model_name,
            "benchmark_name": run.benchmark_name,
            "status": run.status,
            "current_index": run.current_index,
            "total_samples": run.total_samples,
            "samples_completed": stats["total"],
            "samples_correct": stats["correct"],
            "accuracy": stats["accuracy"],
            "accuracy_display": f"{stats['accuracy']}%",
            "avg_tps": stats["avg_tps"],
            "avg_ttft": stats["avg_ttft"],
            "avg_prompt_tps": stats["avg_prompt_tps"],
            "total_tokens": stats["total_tk"],
            "thinking_tokens": stats["think_tk"],
            "response_tokens": stats["resp_tk"],
            "repetition_warnings": len(rep_warnings),
            "safety_metrics": safety_metrics,
            "notes": run.notes or "",
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }


def get_run_meta(run_id: int) -> dict:
    """Benchmark name + context length for one run (service layer).

    Carries the NIAHS 65536 default that previously lived in the router.
    Never raises — unknown runs yield empty defaults.
    """
    benchmark_name = ""
    context_length = None
    try:
        with get_db() as db:
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                benchmark_name = run.benchmark_name or ""
                context_length = run.get_parameters().get("context_length")
                if context_length is None and benchmark_name == "NIAHS":
                    context_length = 65536
    except Exception:
        logger.debug("get_run_meta(%s) failed", run_id, exc_info=True)
    return {"benchmark_name": benchmark_name, "context_length": context_length}


def get_depth_results(run_id: int) -> list[dict]:
    """Per-depth correctness points for NIAHS runs (service layer).

    Expands the multi-needle ``per_depth_correct`` map into one point per
    depth; falls back to one point per Result for legacy single-needle rows.
    """
    with get_db() as db:
        results = db.query(Result).filter(Result.run_id == run_id).all()
        depth_data = []
        for r in results:
            sd = {}
            if r.scoring_details:
                try:
                    sd = json.loads(r.scoring_details)
                except Exception:
                    logger.debug("Failed to parse scoring_details for task %s", r.task_id)
            ctx_len = sd.get("context_length", 0)
            per = sd.get("per_depth_correct")
            if isinstance(per, dict) and per:
                for depth_str, ok in per.items():
                    try:
                        dval = float(depth_str)
                    except Exception:
                        dval = 0
                    depth_data.append({
                        "task_id": f"{r.task_id}@{int(dval * 100)}%",
                        "correct": bool(ok),
                        "depth": dval,
                        "context_length": ctx_len,
                    })
            else:
                depth_data.append({
                    "task_id": r.task_id,
                    "correct": r.correct,
                    "depth": sd.get("depth", 0),
                    "context_length": ctx_len,
                })
        return depth_data


def build_poll_payload(result: dict):
    """Shape a ``poll()`` result dict into the ``GET /api/poll`` response.

    Single builder shared by ``GET /api/poll`` and ``GET /api/poll/stream``
    so the two payloads cannot drift (previously constructed inline twice).
    Kept here (not in api.py) so both router handlers share one shape;
    DataFrame conversion is inlined to avoid an api↔operations import cycle.
    """
    batch_df = result.get("batch_summary_df")
    if batch_df is None or (hasattr(batch_df, "empty") and batch_df.empty):
        batch_summary = []
    else:
        batch_summary = batch_df.to_dict(orient="records")

    metrics = result["metrics"]
    return {
        "telemetry": {
            "cpu_percent": metrics["cpu_percent"],
            "ram_used_gb": metrics["ram_used_gb"],
            "ram_total_gb": metrics["ram_total_gb"],
            "ram_percent": metrics["ram_percent"],
            "gpu_available": metrics["gpu_available"],
            "gpu_name": metrics["gpu_name"],
            "gpu_load": metrics["gpu_load"],
            "vram_total_mb": metrics["vram_total_mb"],
            "vram_used_mb": metrics["vram_used_mb"],
            "vram_percent": metrics["vram_percent"],
        },
        "run_progress": {
            "progress": result["prog_val"],
            "status_md": result["status_md"],
            "active_task": result["active_task"],
            "avg_tps": result["avg_tps"],
            "avg_ttft": result["avg_ttft"],
            "accuracy": result["accuracy"],
            "token_stats": result["token_stats"],
        },
        "batch_progress": {
            "progress": result["batch_prog_val"],
            "status_md": result["batch_status_md"],
            "eta": result["batch_eta_str"],
            "summary": batch_summary,
            "batch_id": result["batch_id_val"],
            "completed": result["batch_done"],
            "total": result["batch_total"],
            "current_benchmark": result["batch_current_name"],
        },
        "active_run_override": result["active_run_override"],
        "live_turn": result.get("live_turn"),
    }


def poll(active_run_id: int | None = None) -> dict:
    """Returns telemetry + run_progress + batch_progress. GPU/PowerShell telemetry cached with 2s TTL; CPU/RAM always fresh. When a batch run completes and another is PENDING, fires active_run_override to show its live progress."""
    metrics, _new_smooth_cpu, _new_smooth_gpu = _update_telemetry_history()

    _cpu_text = f"CPU: {metrics.get('cpu_percent', 0):.1f}%"
    _ram_text = f"RAM: {metrics.get('ram_used_gb', 0):.1f}/{metrics.get('ram_total_gb', 0):.1f} GB"
    _gpu_text = f"GPU: {metrics.get('gpu_name', 'N/A')} ({metrics.get('gpu_load', 0):.1f}%)"
    _vram_text = f"VRAM: {metrics.get('vram_used_mb', 0):.0f}/{metrics.get('vram_total_mb', 0):.0f} MB"

    with _telemetry_lock:
        _hist_slice = telemetry_history[-60:] if telemetry_history else []

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
        bid = _state._active_batch_id
        bst = _state._batch_start_time

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
        lt = get_live_turn_state(active_run_id)
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
