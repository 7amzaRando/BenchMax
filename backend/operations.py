import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import difflib
import secrets
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import httpx
from sqlalchemy import text as sa_text
from sqlalchemy.orm import joinedload

from backend.config import ROOT, EXE_DIR, BENCHMARKS, BENCH_NAMES, DATASETS, PROVIDER_PRESETS
from backend.database import SessionLocal, Run, Result, init_db
from backend.telemetry.monitor import get_system_metrics

logger = logging.getLogger(__name__)

MAX_HISTORY_LEN = 300
telemetry_history: list[dict] = []
_batch_queue: dict[str, list[int]] = {}
_active_batch_id: str | None = None
_batch_start_time: float | None = None
_halt_events: dict[int, threading.Event] = {}
_history_cache: dict = {"data": None, "timestamp": 0.0}
_recent_runs_cache: dict = {"data": None, "timestamp": 0.0}
_CACHE_TTL = 5.0  # seconds
_EMA_ALPHA = 0.15
_telemetry_state = {"smooth_cpu": 0.0, "smooth_gpu": 0.0}
_LB_SUPABASE_KEY = ""
_LB_API_URL = "https://bcbrrsghpynsvsxdsrjn.supabase.co/rest/v1/leaderboard"
_batch_lock = threading.Lock()
_halt_events_lock = threading.Lock()

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
_model_queue_lock = threading.Lock()


def _queue_skip_model_requested() -> bool:
    with _model_queue_lock:
        return _model_queue_state.get("skip_model", False)


def _clear_skip_model_flag():
    with _model_queue_lock:
        _model_queue_state["skip_model"] = False


def _update_telemetry_history(smooth_cpu=0.0, smooth_gpu=0.0) -> tuple[dict, float, float]:
    global telemetry_history, _telemetry_state
    metrics = get_system_metrics()
    raw_cpu = metrics.get("cpu_percent", 0.0)
    raw_gpu = metrics.get("gpu_load", 0.0)
    smooth_cpu = smooth_cpu + _EMA_ALPHA * (raw_cpu - smooth_cpu) if smooth_cpu else raw_cpu
    smooth_gpu = smooth_gpu + _EMA_ALPHA * (raw_gpu - smooth_gpu) if smooth_gpu else raw_gpu
    _telemetry_state["smooth_cpu"] = smooth_cpu
    _telemetry_state["smooth_gpu"] = smooth_gpu
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
            pass
    return row


def _make_client(api_url: str, api_key: str):
    from backend.lm_studio.client import LMStudioClient
    return LMStudioClient(base_url=api_url, api_key=api_key or None)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _instantiate_benchmark(benchmark_name: str, db, client, quick_test=False, hard=False):
    if benchmark_name == "HumanEval":
        from backend.benchmarks.humaneval import HumanEvalBenchmark
        return HumanEvalBenchmark(db, client, quick_test)
    elif benchmark_name == "MMLU-Pro":
        from backend.benchmarks.mmlu_pro import MMLUProBenchmark
        return MMLUProBenchmark(db, client, quick_test)
    elif benchmark_name == "IFEval":
        from backend.benchmarks.ifeval import IFEvalBenchmark
        return IFEvalBenchmark(db, client, quick_test)
    elif benchmark_name == "AIME":
        from backend.benchmarks.aime import AIMEBenchmark
        return AIMEBenchmark(db, client, quick_test)
    elif benchmark_name == "BigCodeBench":
        from backend.benchmarks.bigcodebench import BigCodeBenchBenchmark
        return BigCodeBenchBenchmark(db, client, quick_test, hard=False)
    elif benchmark_name == "BigCodeBench-Hard":
        from backend.benchmarks.bigcodebench import BigCodeBenchBenchmark
        return BigCodeBenchBenchmark(db, client, quick_test, hard=True)
    elif benchmark_name == "BFCL":
        from backend.benchmarks.bfcl import BFCLBenchmark
        return BFCLBenchmark(db, client, quick_test)
    elif benchmark_name == "MCP-Bench":
        from backend.benchmarks.mcp_bench import MCPBenchBenchmark
        return MCPBenchBenchmark(db, client, quick_test)
    elif benchmark_name == "Safety":
        from backend.benchmarks.safety import SafetyBenchmark
        return SafetyBenchmark(db, client, quick_test)
    elif benchmark_name == "LongBench-v2":
        from backend.benchmarks.longbench_v2 import LongBenchV2Benchmark
        return LongBenchV2Benchmark(db, client, quick_test)
    elif benchmark_name == "Aider Polyglot":
        from backend.benchmarks.aider_polyglot import AiderPolyglotBenchmark
        return AiderPolyglotBenchmark(db, client, quick_test)
    elif benchmark_name == "MMMU-Pro":
        from backend.benchmarks.mmmu_pro import MMMUProBenchmark
        return MMMUProBenchmark(db, client, quick_test)
    elif benchmark_name == "LiveBench":
        from backend.benchmarks.livebench import LiveBenchBenchmark
        return LiveBenchBenchmark(db, client, quick_test)
    elif benchmark_name == "LiveCodeBench":
        from backend.benchmarks.livecodebench import LiveCodeBenchBenchmark
        return LiveCodeBenchBenchmark(db, client, quick_test)
    elif benchmark_name == "BenchMax Personal":
        from backend.benchmarks.personal import BenchMaxPersonalBenchmark
        return BenchMaxPersonalBenchmark(db, client, quick_test)
    elif benchmark_name == "BenchMax Lite":
        from backend.benchmarks.lite import BenchMaxLiteBenchmark
        return BenchMaxLiteBenchmark(db, client, quick_test)
    elif benchmark_name == "BenchMax Code":
        from backend.benchmarks.code_bench import BenchMaxCodeBenchmark
        return BenchMaxCodeBenchmark(db, client, quick_test)
    elif benchmark_name == "BenchMax Reason":
        from backend.benchmarks.reason_bench import BenchMaxReasonBenchmark
        return BenchMaxReasonBenchmark(db, client, quick_test)
    elif benchmark_name == "Writing Speed Test":
        from backend.benchmarks.speed_test import WritingSpeedTestBenchmark
        return WritingSpeedTestBenchmark(db, client, quick_test)
    elif benchmark_name == "Coding Speed Test":
        from backend.benchmarks.speed_test import CodingSpeedTestBenchmark
        return CodingSpeedTestBenchmark(db, client, quick_test)
    elif benchmark_name == "BenchMax Tectonic":
        from backend.benchmarks.tectonic import BenchMaxTectonicBenchmark
        return BenchMaxTectonicBenchmark(db, client, quick_test)
    elif benchmark_name == "TruthfulQA":
        from backend.benchmarks.truthfulqa import TruthfulQABenchmark
        return TruthfulQABenchmark(db, client, quick_test)
    raise ValueError(f"Unknown benchmark: {benchmark_name}")


def _start_benchmark_thread(
    run_id: int,
    api_url: str,
    api_key: str,
    temp: float,
    max_tokens: int,
    sys_prompt: str,
    benchmark_name: str = "HumanEval",
    quick_test: bool = False,
    _remaining_ids: Optional[list[int]] = None,
):
    def _run():
        db = SessionLocal()
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                logger.error(f"Run {run_id} not found for thread start.")
                return
            params = run.get_parameters()
            if temp is not None:
                params.setdefault("temperature", temp)
            elif "temperature" in params:
                del params["temperature"]
            params.setdefault("max_completion_tokens", max_tokens)
            params.setdefault("system_prompt", sys_prompt)
            params.setdefault("api_key", api_key)
            with _halt_events_lock:
                halt_ev = _halt_events.get(run_id)
                if halt_ev is None:
                    halt_ev = threading.Event()
                    _halt_events[run_id] = halt_ev
            params["_halt_event"] = halt_ev
            params_for_db = {k: v for k, v in params.items() if k != "_halt_event"}
            run.set_parameters(params_for_db)
            db.commit()

            client = __import__("backend.lm_studio.client", fromlist=["LMStudioClient"]).LMStudioClient(
                base_url=api_url,
                api_key=api_key or None,
            )
            bench = _instantiate_benchmark(benchmark_name, db, client, quick_test)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(bench.run_evaluation(run_id, params))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Benchmark thread fatal error: {e}", exc_info=True)
            try:
                run = db.query(Run).filter(Run.id == run_id).first()
                if run and run.status not in ("COMPLETED", "HALTED", "FAILED"):
                    run.status = "FAILED"
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()
        if _remaining_ids:
            _chain_batch(_remaining_ids, api_url, api_key, temp, max_tokens, sys_prompt, quick_test)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _chain_batch(remaining_ids, api_url, api_key, temp, max_tokens, sys_prompt, quick_test):
    """When a batch run completes, finds the next PENDING run via _remaining_ids, resets halt_ev, and triggers it. Guarded by _batch_lock for _active_batch_id."""
    if not remaining_ids:
        return
    next_run_id = remaining_ids[0]
    rest = remaining_ids[1:] if len(remaining_ids) > 1 else None
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == next_run_id).first()
        if not run:
            return
        bn = run.benchmark_name
        _start_benchmark_thread(
            next_run_id, api_url, api_key, temp, max_tokens, sys_prompt,
            benchmark_name=bn, quick_test=quick_test, _remaining_ids=rest,
        )
    finally:
        db.close()


def _build_batch_summary(batch_id: str) -> pd.DataFrame:
    db = SessionLocal()
    try:
        runs = db.query(Run).options(joinedload(Run.results)).filter(Run.batch_id == batch_id).order_by(Run.id).all()
        rows = []
        for r in runs:
            results = r.results
            n = len(results)
            ok = sum(1 for res in results if res.correct)
            tps_vals = [res.tps for res in results if res.tps and res.tps > 0]
            ttft_vals = [res.ttft for res in results if res.ttft and res.ttft > 0]
            total_tk = sum((res.thinking_tokens or 0) + (res.response_tokens or 0) for res in results)
            rows.append({
                "Run ID": r.id,
                "Benchmark": r.benchmark_name,
                "Status": r.status,
                "Correct": ok,
                "Total": n,
                "Accuracy": f"{round(ok/n*100, 1)}%" if n else "0%",
                "Avg TPS": round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0,
                "Avg TTFT": f"{round(sum(ttft_vals) / len(ttft_vals), 3)}s" if ttft_vals else "0s",
                "Total Tokens": total_tk,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    finally:
        db.close()


def _build_tps_histogram(results, bins=15) -> pd.DataFrame:
    tps_vals = [r.tps for r in results if r.tps and r.tps > 0]
    if not tps_vals:
        return pd.DataFrame()
    if len(set(tps_vals)) <= 1:
        val = tps_vals[0]
        return pd.DataFrame({"TPS Range": [f"{round(val, 1)}"], "Count": [len(tps_vals)]})
    counts, edges = pd.cut(pd.Series(tps_vals), bins=bins, retbins=True, precision=2)
    bin_labels = [f"{round(edges[i], 1)}-{round(edges[i+1], 1)}" for i in range(len(edges) - 1)]
    df = pd.DataFrame({"TPS Range": bin_labels, "Count": counts.value_counts(sort=False).values})
    return df


def _build_ttft_histogram(results, bins=15) -> pd.DataFrame:
    ttft_vals = [r.ttft for r in results if r.ttft and r.ttft > 0]
    if not ttft_vals:
        return pd.DataFrame()
    if len(set(ttft_vals)) <= 1:
        val = ttft_vals[0]
        return pd.DataFrame({"TTFT Range (s)": [f"{round(val, 3)}"], "Count": [len(ttft_vals)]})
    counts, edges = pd.cut(pd.Series(ttft_vals), bins=bins, retbins=True, precision=3)
    bin_labels = [f"{round(edges[i], 3)}-{round(edges[i+1], 3)}" for i in range(len(edges) - 1)]
    df = pd.DataFrame({"TTFT Range (s)": bin_labels, "Count": counts.value_counts(sort=False).values})
    return df


def _build_aggregated_token_chart(results) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Sample": r.task_id,
            "Thinking": r.thinking_tokens or 0,
            "Response": r.response_tokens or 0,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _build_per_category_chart(results, benchmark_name="") -> pd.DataFrame:
    rows = []
    for r in results:
        extra = {}
        if r.scoring_details:
            try:
                extra = json.loads(r.scoring_details)
            except Exception:
                pass
        cat = extra.get("category", r.task_id.split("/")[0] if "/" in r.task_id else benchmark_name)
        rows.append({"Category": cat, "Correct": 1 if r.correct else 0, "Total": 1})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    grouped = df.groupby("Category").agg({"Correct": "sum", "Total": "sum"}).reset_index()
    grouped["Accuracy"] = (grouped["Correct"] / grouped["Total"] * 100).round(1)
    return grouped


def _build_batch_latency_chart(runs, db) -> pd.DataFrame:
    rows = []
    for r in runs:
        results = db.query(Result).filter(Result.run_id == r.id).all()
        tps_vals = [res.tps for res in results if res.tps and res.tps > 0]
        ttft_vals = [res.ttft for res in results if res.ttft and res.ttft > 0]
        rows.append({
            "Benchmark": r.benchmark_name,
            "Avg TPS": round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0,
            "Avg TTFT (s)": round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _scan_datasets() -> pd.DataFrame:
    import json as _json
    rows = []
    for name, (rel_path, _) in DATASETS.items():
        found = False
        sample_count = "—"
        # rel_path is like "data/humaneval_full.json" or "data/bfcl/bfcl_full.json"
        # Check relative to ROOT, CWD, and EXE_DIR
        candidates = [ROOT / rel_path]
        if not found:
            candidates.append(Path.cwd() / rel_path)
        if EXE_DIR:
            candidates.append(EXE_DIR / rel_path)
            candidates.append(EXE_DIR.parent / rel_path)
        for p in candidates:
            if p.exists():
                found = True
                try:
                    data = _json.loads(p.read_text(encoding="utf-8"))
                    sample_count = str(len(data)) if isinstance(data, list) else str(len(data.keys()))
                except Exception:
                    sample_count = "?"
                break
        rows.append({
            "Benchmark": name,
            "Installed": "✅" if found else "❌",
            "Samples": sample_count,
        })
    return pd.DataFrame(rows)


def connect_lm_studio(api_url: str, api_key: str = "") -> tuple[str, pd.DataFrame, list, dict]:
    """Hits /v1/models (simple list) and /api/v0/models (metadata: context length) and merges them."""
    from backend.lm_studio.client import LMStudioClient
    metadata = {}
    error_msg = ""
    try:
        client = LMStudioClient(base_url=api_url, api_key=api_key or None)
        models_raw = client.get_loaded_models()
        models_raw = asyncio.run(models_raw) if hasattr(models_raw, '__await__') else models_raw
        if not models_raw:
            status = "Connected, but no models loaded."
            df = pd.DataFrame(columns=["id"])
            choices = []
        else:
            model_ids = [m.get("id", f"model_{i}") for i, m in enumerate(models_raw)]
            df = pd.DataFrame({"id": model_ids, "Model": model_ids})
            choices = model_ids
            status = f"🟢 Connected — {len(model_ids)} model(s) loaded."

        meta = client.get_models_metadata()
        meta = asyncio.run(meta) if hasattr(meta, '__await__') else meta
        if meta:
            metadata = meta
            for mid in meta:
                ctx = meta[mid].get("max_context_length", "?")
                status += f"\n  {mid}: context={ctx}"
    except Exception as e:
        status = f"Connection failed: {e}"
        df = pd.DataFrame(columns=["id"])
        choices = []
        error_msg = str(e)

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
) -> tuple[int | None, str]:
    """Creates a Run row in DB, spawns a daemon thread for evaluation, and returns (run_id, message). Daemon thread so it does not block process exit."""
    db = SessionLocal()
    try:
        params_dict = {"api_url": api_url, "max_completion_tokens": max_tokens, "system_prompt": sys_prompt}
        if temp is not None:
            params_dict["temperature"] = temp
        params_dict["quick_test"] = quick_test
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

        _start_benchmark_thread(
            run_id, api_url, api_key, temp, max_tokens, sys_prompt,
            benchmark_name=benchmark_name, quick_test=quick_test,
        )
        return run_id, f"Run {run_id} started."
    except Exception as e:
        db.rollback()
        logger.error(f"trigger_run failed: {e}", exc_info=True)
        return None, str(e)
    finally:
        db.close()


def start_batch(
    selected_model: str,
    selected_benchmarks: list[str],
    api_url: str,
    api_key: str = "",
    temp: float = 0.0,
    max_tokens: int = 2048,
    sys_prompt: str = "",
    quick_test: bool = False,
) -> tuple[int | None, str, str, pd.DataFrame, str]:
    """Creates one Run per benchmark with a shared batch_id UUID, chains them sequentially via _remaining_ids. Captures api_url/api_key in each Run's parameters so resumes are independent."""
    if not selected_benchmarks:
        return None, "", "No benchmarks selected.", pd.DataFrame(), ""

    batch_id = str(uuid.uuid4())
    run_ids = []
    db = SessionLocal()
    try:
        for bn in selected_benchmarks:
            params_dict = {"api_url": api_url, "max_completion_tokens": max_tokens, "system_prompt": sys_prompt}
            if temp is not None:
                params_dict["temperature"] = temp
            params_dict["quick_test"] = quick_test
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
            _batch_queue[batch_id] = run_ids
            global _active_batch_id, _batch_start_time
            _active_batch_id = batch_id
            _batch_start_time = time.time()

        summary_df = _build_batch_summary(batch_id)
        first_id = run_ids[0] if run_ids else None

        _start_benchmark_thread(
            run_ids[0], api_url, api_key, temp, max_tokens, sys_prompt,
            benchmark_name=selected_benchmarks[0], quick_test=quick_test,
            _remaining_ids=run_ids[1:] if len(run_ids) > 1 else None,
        )
        return first_id, batch_id, f"Batch {batch_id[:8]} started — {len(run_ids)} benchmarks.", summary_df, batch_id[:8]
    except Exception as e:
        db.rollback()
        logger.error(f"start_batch failed: {e}", exc_info=True)
        return None, "", str(e), pd.DataFrame(), ""
    finally:
        db.close()


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
):
    """
    Loops through (model, benchmarks) pairs: loads model via LM Studio API, runs all benchmarks
    sequentially, then unloads model. Checks halt at 3 points (between models, after load, between
    benchmarks). Captures instance_id from load response for unload.
    """
    import httpx as _httpx

    client = _make_client(api_url, api_key)

    with _model_queue_lock:
        _model_queue_state["queue_id"] = queue_id
        _model_queue_state["models"] = [m for m, _ in model_benchmarks]
        _model_queue_state["total_models"] = len(model_benchmarks)
        _model_queue_state["status"] = "running"
        _model_queue_state["api_url"] = api_url
        _model_queue_state["api_key"] = api_key

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        for mi, (model_id, benches) in enumerate(model_benchmarks):
            if _queue_halted() or _queue_skip_model_requested():
                break

            with _model_queue_lock:
                _model_queue_state["current_model_index"] = mi
                _model_queue_state["current_benchmark"] = f"Loading {model_id}..."

            # Load model
            try:
                load_result = loop.run_until_complete(client.load_model(model_id))
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
                    loop.run_until_complete(client.unload_model(model_id))
                except Exception:
                    pass
                break

            # Create Run records for each benchmark on this model
            db = SessionLocal()
            run_ids_for_model = []
            try:
                for bn in benches:
                    mparams = {"api_url": api_url, "max_completion_tokens": max_tokens, "system_prompt": sys_prompt}
                    if temp is not None:
                        mparams["temperature"] = temp
                    mparams["quick_test"] = quick_test
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
            finally:
                db.close()

            with _model_queue_lock:
                _model_queue_state["current_benchmark"] = f"Running on {model_id}"
                _model_queue_state["benchmarks_per_model"][model_id] = benches

            # Run benchmarks sequentially on this model
            for bi, bn in enumerate(benches):
                if _queue_halted():
                    break
                _clear_skip_model_flag()

                with _model_queue_lock:
                    _model_queue_state["current_benchmark"] = f"{model_id} — {bn} ({bi+1}/{len(benches)})"

                db2 = SessionLocal()
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

                    bench = _instantiate_benchmark(bn, db2, client, quick_test)
                    if not bench:
                        run_rec.status = "FAILED"
                        db2.commit()
                        continue

                    loop.run_until_complete(bench.run_evaluation(run_rec.id, params))
                except Exception as e:
                    logger.error(f"Model queue benchmark error ({model_id} / {bn}): {e}", exc_info=True)
                    try:
                        run_rec = db2.query(Run).filter(Run.id == run_ids_for_model[bi]).first()
                        if run_rec and run_rec.status not in ("COMPLETED", "HALTED", "FAILED"):
                            run_rec.status = "FAILED"
                            db2.commit()
                    except Exception:
                        pass
                finally:
                    db2.close()

                # After each benchmark, skip remaining benchmarks on this model if requested
                if _queue_skip_model_requested():
                    break

            # Unload model (only if not halted — halt has its own cleanup)
            if not _queue_halted():
                with _model_queue_lock:
                    _model_queue_state["current_benchmark"] = f"Unloading {model_id}..."
                try:
                    loop.run_until_complete(client.unload_model(model_id))
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Model unload warning for {model_id}: {e}")

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
                    hloop = asyncio.new_event_loop()
                    asyncio.set_event_loop(hloop)
                    try:
                        hloop.run_until_complete(halt_client.unload_model(model_to_unload))
                    finally:
                        hloop.close()
                    logger.info(f"Halt cleanup: unloaded model {model_to_unload}")
                except Exception as e:
                    logger.warning(f"Halt cleanup: unload of {model_to_unload} failed: {e}")
            with _model_queue_lock:
                _model_queue_state["status"] = "idle"
                _model_queue_state["queue_id"] = None
            with _batch_lock:
                global _active_batch_id, _batch_start_time
                _active_batch_id = None
                _batch_start_time = None
        try:
            loop.run_until_complete(client.close())
        except Exception:
            pass
        loop.close()


def start_model_queue(
    model_benchmarks: list[tuple[str, list[str]]],
    api_url: str,
    api_key: str = "",
    temp: float = 0.0,
    max_tokens: int = 2048,
    sys_prompt: str = "",
    quick_test: bool = False,
) -> tuple[str, str]:
    if not model_benchmarks:
        return "", "No models selected."

    queue_id = str(uuid.uuid4())
    total_models = len(model_benchmarks)
    total_benches = sum(len(b) for _, b in model_benchmarks)

    thread = threading.Thread(
        target=_run_model_queue_in_thread,
        args=(queue_id, model_benchmarks, api_url, api_key, temp, max_tokens, sys_prompt, quick_test),
        daemon=True,
    )
    thread.start()

    return queue_id, f"Model queue started — {total_models} model(s), {total_benches} benchmark(s)."


def get_model_queue_state() -> dict:
    with _model_queue_lock:
        return dict(_model_queue_state)


def halt_model_queue() -> str:
    qid = None
    with _model_queue_lock:
        if _model_queue_state["status"] not in ("running", "pending"):
            return "No active model queue."
        _model_queue_state["status"] = "halted"
        _model_queue_state["message"] = "Model queue halting — finishing current sample..."
        qid = _model_queue_state["queue_id"]
    if qid:
        db = SessionLocal()
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
        finally:
            db.close()
    return "Model queue halted — cleaning up..."


def skip_current_model() -> str:
    with _model_queue_lock:
        if _model_queue_state["status"] != "running":
            return "No active model queue."
        _model_queue_state["skip_model"] = True
        _model_queue_state["message"] = "Skipping current model..."
    # Signal the running benchmark's halt event to stop early
    qid = _model_queue_state.get("queue_id")
    if qid:
        db = SessionLocal()
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
        finally:
            db.close()
    return "Skipping current model..."



def pause_run(run_id: int) -> str:
    db = SessionLocal()
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
        return str(e)
    finally:
        db.close()


def resume_run(
    run_id: int,
    api_url: str,
    api_key: str = "",
    temp: float = 0.0,
    max_tokens: int = 2048,
    sys_prompt: str = "",
    quick_test: bool = False,
) -> str:
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return "Run not found."
        if run.status != "PAUSED":
            return f"Cannot resume — status is {run.status}."
        run.status = "RUNNING"
        db.commit()
        with _halt_events_lock:
            halt_ev = _halt_events.get(run_id)
            if halt_ev is None:
                halt_ev = threading.Event()
                _halt_events[run_id] = halt_ev

        _start_benchmark_thread(
            run_id, api_url, api_key, temp, max_tokens, sys_prompt,
            benchmark_name=run.benchmark_name, quick_test=quick_test,
        )
        return f"Run {run_id} resumed."
    except Exception as e:
        return str(e)
    finally:
        db.close()


def halt_run(run_id: int) -> str:
    db = SessionLocal()
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
        return str(e)
    finally:
        db.close()


def load_history() -> pd.DataFrame:
    db = SessionLocal()
    try:
        runs = db.query(Run).options(joinedload(Run.results)).filter(Run.status != "PENDING").order_by(Run.id.desc()).all()
        rows = []
        for r in runs:
            results = r.results  # already loaded via joinedload
            n = len(results)
            ok = sum(1 for res in results if res.correct)
            tps_vals = [res.tps for res in results if res.tps and res.tps > 0]
            ttft_vals = [res.ttft for res in results if res.ttft and res.ttft > 0]
            total_tk = sum((res.thinking_tokens or 0) + (res.response_tokens or 0) for res in results)
            avg_tokens = round(total_tk / n, 1) if n else 0
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

            rows.append({
                "Run ID": r.id,
                "Model": r.model_name,
                "Benchmark": r.benchmark_name,
                "Status": display_status,
                "Progress": f"{r.current_index}/{r.total_samples}",
                "Correct": ok,
                "Total": n,
                "Accuracy": f"{round(ok/n*100, 1)}%" if n else "0%",
                "Avg TPS": round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0,
                "Avg TTFT": round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0,
                "Avg Tokens": avg_tokens,
                "Total Tokens": total_tk,
                "Duration": duration_str,
                "Batch": r.batch_id or "",
                "Created": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    finally:
        db.close()


def load_run_details(run_id_str: str) -> tuple[str, pd.DataFrame, list, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads Run + all Results via joinedload, computes summary metrics (avg_tps, ttft, accuracy, token breakdown) and chart data (per-category, token, histograms). Accuracy = correct/total with 0-division guard."""
    db = SessionLocal()
    try:
        run_id = int(run_id_str)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return "Run not found.", pd.DataFrame(), [], pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        results = db.query(Result).filter(Result.run_id == run_id).order_by(Result.id).all()
        n = len(results)
        ok = sum(1 for r in results if r.correct)
        tps_vals = [r.tps for r in results if r.tps and r.tps > 0]
        ttft_vals = [r.ttft for r in results if r.ttft and r.ttft > 0]
        total_tk = sum((r.thinking_tokens or 0) + (r.response_tokens or 0) for r in results)
        think_tk = sum(r.thinking_tokens or 0 for r in results)
        resp_tk = sum(r.response_tokens or 0 for r in results)

        params_dict = run.get_parameters()
        quick_test = params_dict.get("quick_test", False)

        summary_md = (
            f"**Run {run.id} — {run.benchmark_name}  \n"
            f"Model: `{run.model_name}`  \n"
            f"Status: **{run.status}**  |  "
            f"Accuracy: **{ok}/{n} ({round(ok/n*100, 1) if n else 0}%)**  \n"
            f"Avg TPS: `{round(sum(tps_vals)/len(tps_vals), 1) if tps_vals else 0}`  |  "
            f"Avg TTFT: `{round(sum(ttft_vals)/len(ttft_vals), 3) if ttft_vals else 0}s`  \n"
            f"Total Tokens: {total_tk}  "
            f"(Thinking: {round(think_tk / (think_tk + resp_tk) * 100, 1) if (think_tk + resp_tk) else 0}%, "
            f"Response: {round(resp_tk / (think_tk + resp_tk) * 100, 1) if (think_tk + resp_tk) else 0}%)  \n"
            f"Created: {run.created_at.strftime('%Y-%m-%d %H:%M:%S') if run.created_at else 'N/A'}"
        )

        rows = []
        failed_tasks = []
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
            rows.append(row)
            if not r.correct and r.task_id != "personal_bms_score" and r.task_id != "lite_bms_score":
                failed_tasks.append(r.task_id)

        samples_df = pd.DataFrame(rows) if rows else pd.DataFrame()
        token_df = _build_aggregated_token_chart(results)
        ttft_hist = _build_ttft_histogram(results)
        tps_hist = _build_tps_histogram(results)
        cat_chart = _build_per_category_chart(results, run.benchmark_name)

        return summary_md, samples_df, failed_tasks, token_df, ttft_hist, tps_hist, cat_chart
    except Exception as e:
        logger.error(f"load_run_details error: {e}", exc_info=True)
        return f"Error: {e}", pd.DataFrame(), [], pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    finally:
        db.close()


def analyze_run(run_id_str: str) -> tuple[str, pd.DataFrame, list, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Alias for load_run_details — provided for API endpoint parity (Results Analyzer)."""
    return load_run_details(run_id_str)


def load_batch_summary(batch_id_str: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_df = _build_batch_summary(batch_id_str)
    db = SessionLocal()
    try:
        runs = db.query(Run).filter(Run.batch_id == batch_id_str).order_by(Run.id).all()
        chart_rows = []
        for r in runs:
            chart_rows.append({
                "Benchmark": r.benchmark_name,
                "Status": r.status,
            })
        chart_df = pd.DataFrame(chart_rows) if chart_rows else pd.DataFrame()
        latency_df = _build_batch_latency_chart(runs, db)
    finally:
        db.close()
    return summary_df, chart_df, latency_df


def load_recent_runs() -> list[str]:
    db = SessionLocal()
    try:
        runs = db.query(Run).filter(Run.status != "PENDING").order_by(Run.id.desc()).limit(20).all()
        return [f"Run #{r.id} - {r.benchmark_name} ({r.status})" for r in runs]
    finally:
        db.close()


def load_leaderboard() -> pd.DataFrame:
    db = SessionLocal()
    try:
        runs = db.query(Run).options(joinedload(Run.results)).filter(Run.status.in_(["COMPLETED", "FAILED"])).order_by(Run.id.desc()).all()
        rows = []
        for r in runs:
            results = r.results
            n = len(results)
            ok = sum(1 for res in results if res.correct)
            accuracy = round(ok / n * 100, 1) if n else 0.0
            tps_vals = [res.tps for res in results if res.tps and res.tps > 0]
            avg_tps = round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0
            ttft_vals = [res.ttft for res in results if res.ttft and res.ttft > 0]
            avg_ttft = round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0
            total_tk = sum((res.thinking_tokens or 0) + (res.response_tokens or 0) for res in results)
            params = r.get_parameters()
            quick_test = params.get("quick_test", False)
            rows.append({
                "Run ID": r.id,
                "Model": r.model_name,
                "Benchmark": r.benchmark_name,
                "Accuracy": f"{accuracy}%",
                "Avg TPS": avg_tps,
                "Avg TTFT": avg_ttft,
                "Passed": f"{ok}/{n}",
                "Tokens": total_tk,
                "Date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                "status": r.status,
                "QuickTest": quick_test,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    finally:
        db.close()


def delete_leaderboard_entry(run_id_str: str) -> tuple[pd.DataFrame, str]:
    db = SessionLocal()
    try:
        run_id = int(run_id_str)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return load_leaderboard(), "Run not found."
        db.delete(run)
        db.commit()
        return load_leaderboard(), f"Run {run_id} deleted."
    except Exception as e:
        return load_leaderboard(), str(e)
    finally:
        db.close()


def clear_all_history(confirm_text: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    if confirm_text != "CONFIRM":
        h = load_history()
        lb = load_leaderboard()
        return h, lb, "Type CONFIRM to clear all history."

    db = SessionLocal()
    try:
        db.query(Result).delete()
        db.query(Run).delete()
        db.commit()
        h = pd.DataFrame()
        lb = pd.DataFrame()
        return h, lb, "All history cleared."
    except Exception as e:
        return load_history(), load_leaderboard(), str(e)
    finally:
        db.close()


def load_cross_comparison(run_ids_csv: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not run_ids_csv:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    ids = [int(x.strip()) for x in run_ids_csv.split(",") if x.strip().isdigit()]
    if not ids:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    db = SessionLocal()
    try:
        acc_rows = []
        lat_rows = []
        tok_rows = []
        for rid in ids:
            run = db.query(Run).options(joinedload(Run.results)).filter(Run.id == rid).first()
            if not run:
                continue
            results = run.results
            n = len(results)
            ok = sum(1 for r in results if r.correct)
            tps_vals = [r.tps for r in results if r.tps and r.tps > 0]
            ttft_vals = [r.ttft for r in results if r.ttft and r.ttft > 0]
            total_tk = sum((r.thinking_tokens or 0) + (r.response_tokens or 0) for r in results)
            label = f"#{rid} {run.benchmark_name}"
            acc_rows.append({
                "Run": label,
                "Accuracy": round(ok / n * 100, 1) if n else 0,
                "Correct": ok,
                "Total": n,
            })
            lat_rows.append({
                "Run": label,
                "Avg TPS": round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0,
                "Avg TTFT (s)": round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0,
            })
            tok_rows.append({
                "Run": label,
                "Thinking": sum(r.thinking_tokens or 0 for r in results),
                "Response": sum(r.response_tokens or 0 for r in results),
                "Total": total_tk,
            })
        return (
            pd.DataFrame(acc_rows) if acc_rows else pd.DataFrame(),
            pd.DataFrame(lat_rows) if lat_rows else pd.DataFrame(),
            pd.DataFrame(tok_rows) if tok_rows else pd.DataFrame(),
        )
    finally:
        db.close()


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
    return None, f"Unsupported format: {fmt}"


def export_results(run_id_str: str, format_type: str) -> tuple[str | None, str]:
    """Exports a single run's results as CSV or JSON. Includes per-sample correctness, timing, tokens, and errors."""
    db = SessionLocal()
    try:
        run_id = int(run_id_str)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return None, "Run not found."
        results = db.query(Result).filter(Result.run_id == run_id).order_by(Result.id).all()
        rows = []
        for r in results:
            row = {
                "run_id": r.run_id,
                "task_id": r.task_id,
                "correct": r.correct,
                "elapsed_time": r.elapsed_time,
                "tps": r.tps,
                "ttft": r.ttft,
                "thinking_tokens": r.thinking_tokens,
                "response_tokens": r.response_tokens,
                "error_message": r.error_message,
            }
            row = _add_scoring_columns(row, r)
            rows.append(row)
        if not rows:
            return None, "No results to export."
        df = pd.DataFrame(rows)
        return _export_dataframe(df, f"run_{run_id}", format_type)
    finally:
        db.close()


def export_batch_results(batch_id: str, format_type: str) -> tuple[str | None, str]:
    """Exports all results across a batch as CSV or JSON. Same fields as export_results but aggregated by run within the batch."""
    db = SessionLocal()
    try:
        runs = db.query(Run).filter(Run.batch_id == batch_id).order_by(Run.id).all()
        if not runs:
            return None, "Batch not found."
        results = db.query(Result).filter(
            Result.run_id.in_([r.id for r in runs])
        ).order_by(Result.run_id, Result.id).all()
        rows = []
        for r in results:
            row = {
                "run_id": r.run_id,
                "task_id": r.task_id,
                "correct": r.correct,
                "elapsed_time": r.elapsed_time,
                "tps": r.tps,
                "ttft": r.ttft,
                "thinking_tokens": r.thinking_tokens,
                "response_tokens": r.response_tokens,
                "error_message": r.error_message,
            }
            row = _add_scoring_columns(row, r)
            rows.append(row)
        if not rows:
            return None, "No results to export."
        df = pd.DataFrame(rows)
        return _export_dataframe(df, f"batch_{batch_id[:8]}", format_type)
    finally:
        db.close()


def export_telemetry() -> tuple[str | None, str]:
    """Exports the in-memory telemetry history buffer as CSV (timestamp, CPU, RAM, GPU load, VRAM)."""
    if not telemetry_history:
        return None, "No telemetry data recorded."
    df = pd.DataFrame(telemetry_history)
    return _export_dataframe(df, "telemetry", "CSV")


def export_all_history() -> tuple[str | None, str]:
    """Exports all completed/failed runs as CSV via load_history(). Includes per-run summary metrics."""
    return _export_dataframe(load_history(), "all_history", "CSV")


def generate_diff(run_id_str: str, task_id: str) -> str:
    db = SessionLocal()
    try:
        run_id = int(run_id_str)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return "<p>Run not found.</p>"
        bench = _instantiate_benchmark(run.benchmark_name, db, None)
        dataset = bench.load_dataset()
        sample = next((s for s in dataset if s.get("task_id") == task_id), None)
        if not sample:
            import re
            m = re.match(r"sample_(\d+)", task_id)
            if m:
                idx = int(m.group(1))
                if 0 <= idx < len(dataset):
                    sample = dataset[idx]
            if not sample:
                return f"<p>Dataset record for {task_id} not found.</p>"
        result = db.query(Result).filter(
            Result.run_id == run_id, Result.task_id == task_id
        ).first()
        if not result:
            return f"<p>Result for {task_id} not found.</p>"
        result_data = {
            "extracted_code": result.extracted_code or "",
            "raw_response": result.raw_response or "",
        }
        html = bench.generate_diff(sample, result_data)
        return html
    except Exception as e:
        logger.error(f"generate_diff error: {e}", exc_info=True)
        return f"<p>Error: {e}</p>"
    finally:
        db.close()


def install_dataset(bench_name: str, hf_token: str = "") -> str:
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

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=120, env=env,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode == 0:
            return f"✅ {bench_name} installed successfully."
        else:
            return f"❌ Installation failed:\n{output[:500]}"
    except subprocess.TimeoutExpired:
        return f"❌ Installation timed out for {bench_name}."
    except Exception as e:
        return f"❌ Error: {e}"


def install_all_missing(hf_token: str = "") -> str:
    results = []
    for name in BENCH_NAMES:
        entry = DATASETS.get(name)
        if not entry:
            continue
        rel_path, script_rel = entry
        found = False
        candidates = [ROOT / rel_path, Path.cwd() / rel_path]
        if EXE_DIR:
            candidates.extend([EXE_DIR / rel_path, EXE_DIR.parent / rel_path])
        for p in candidates:
            if p.exists():
                found = True
                break
        if found:
            continue
        status = install_dataset(name, hf_token)
        results.append(f"{name}: {status}")
    return "\n".join(results) if results else "All datasets already installed."


def download_runtimes() -> str:
    script = ROOT / "scripts" / "setup_runtimes.py"
    if not script.exists():
        return "Setup script not found: scripts/setup_runtimes.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=300,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode == 0:
            return "Runtimes installed successfully."
        else:
            return f"Installation failed:\n{output[:500]}"
    except subprocess.TimeoutExpired:
        return "Installation timed out (300s). Some runtimes may be large; try again."
    except Exception as e:
        return f"Error: {e}"


def update_context_window(model_id: str, metadata: dict) -> str:
    if not model_id:
        return "N/A"
    ctx = None
    if metadata and model_id in metadata:
        ctx = metadata[model_id].get("max_context_length")
    if ctx:
        if ctx >= 1024:
            return f"{round(ctx / 1024)}K"
        return str(ctx)
    return "N/A"


def update_ctx_warning(model_id: str, max_tokens: int, metadata: dict) -> str:
    if not model_id or not metadata:
        return ""
    meta = metadata.get(model_id, {})
    ctx = meta.get("max_context_length")
    if ctx and max_tokens and max_tokens > ctx:
        return f"⚠️ Max tokens ({max_tokens}) exceeds context window ({ctx})"
    return ""


HF_TOKEN_FILE = ROOT / "records" / ".hf_token"


def _load_hf_token() -> str:
    if HF_TOKEN_FILE.exists():
        try:
            return HF_TOKEN_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
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
    global _LB_SUPABASE_KEY
    _LB_SUPABASE_KEY = key
    try:
        os.makedirs(LB_SETTINGS_FILE.parent, exist_ok=True)
        LB_SETTINGS_FILE.write_text(key, encoding="utf-8")
        return "API key saved."
    except Exception as e:
        return f"Failed to save: {e}"


def load_lb_settings() -> str:
    global _LB_SUPABASE_KEY
    if _LB_SUPABASE_KEY:
        return _LB_SUPABASE_KEY
    if LB_SETTINGS_FILE.exists():
        try:
            _LB_SUPABASE_KEY = LB_SETTINGS_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return _LB_SUPABASE_KEY


def sync_to_online_leaderboard(_trigger=0, api_key: str | None = None) -> str:
    try:
        key = api_key or load_lb_settings()
        if not key:
            return "No API key configured."
        db = SessionLocal()
        try:
            runs = db.query(Run).options(joinedload(Run.results)).filter(Run.status.in_(["COMPLETED", "FAILED"])).order_by(Run.id.desc()).all()
            if not runs:
                return "No completed runs to sync."
            records = []
            for r in runs:
                results = r.results
                n = len(results)
                ok = sum(1 for res in results if res.correct)
                accuracy = round(ok / n * 100, 1) if n else 0.0
                tps_vals = [res.tps for res in results if res.tps and res.tps > 0]
                ttft_vals = [res.ttft for res in results if res.ttft and res.ttft > 0]
                avg_tps = round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0
                avg_ttft = round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0
                records.append({
                    "id": secrets.token_hex(8),
                    "benchmark_name": r.benchmark_name,
                    "model_name": r.model_name,
                    "accuracy": accuracy,
                    "samples": n,
                    "passed": ok,
                    "avg_tps": avg_tps,
                    "avg_ttft": avg_ttft,
                    "total_tokens": sum((res.thinking_tokens or 0) + (res.response_tokens or 0) for res in results),
                    "timestamp": r.created_at.isoformat() if r.created_at else "",
                })
        finally:
            db.close()
        headers = {
            "Content-Type": "application/json",
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        res = httpx.post(
            _LB_API_URL,
            json=records,
            headers=headers,
            timeout=30,
        )
        if res.status_code in (200, 201):
            return f"Synced {len(records)} entries."
        else:
            return f"Sync failed ({res.status_code}): {res.text[:200]}"
    except Exception as e:
        return f"Sync error: {e}"


def get_active_batch_id():
    with _batch_lock:
        return _active_batch_id


def get_batch_start_time():
    with _batch_lock:
        return _batch_start_time


def poll(
    active_run_id: int | None = None,
    smooth_cpu: float = 0.0,
    smooth_gpu: float = 0.0,
) -> tuple:
    """Returns telemetry + run_progress + batch_progress. GPU/PowerShell telemetry cached with 2s TTL; CPU/RAM always fresh. When a batch run completes and another is PENDING, fires active_run_override to show its live progress."""
    metrics, new_smooth_cpu, new_smooth_gpu = _update_telemetry_history(smooth_cpu, smooth_gpu)

    cpu_text = f"CPU: {metrics.get('cpu_percent', 0):.1f}%"
    ram_text = f"RAM: {metrics.get('ram_used_gb', 0):.1f}/{metrics.get('ram_total_gb', 0):.1f} GB"
    gpu_text = f"GPU: {metrics.get('gpu_name', 'N/A')} ({metrics.get('gpu_load', 0):.1f}%)"
    vram_text = f"VRAM: {metrics.get('vram_used_mb', 0):.0f}/{metrics.get('vram_total_mb', 0):.0f} MB"

    cpu_df = pd.DataFrame(telemetry_history[-60:]) if telemetry_history else pd.DataFrame()
    ram_df = cpu_df[["timestamp", "ram_used_gb", "ram_total_gb"]].copy() if not cpu_df.empty else pd.DataFrame()
    gpu_df = pd.DataFrame(telemetry_history[-60:])[["timestamp", "gpu_load"]].copy() if telemetry_history else pd.DataFrame()
    vram_df = pd.DataFrame(telemetry_history[-60:])[["timestamp", "vram_used_mb", "vram_total_mb"]].copy() if telemetry_history else pd.DataFrame()

    prog_val = 0.0
    status_md = ""
    active_task = ""
    avg_tps = 0.0
    avg_ttft = 0.0
    accuracy = ""
    token_stats = ""

    if active_run_id:
        db = SessionLocal()
        try:
            run = db.query(Run).options(joinedload(Run.results)).filter(Run.id == active_run_id).first()
            if run:
                total = run.total_samples or 1
                current = run.current_index or 0
                prog_val = min(current / total, 1.0)
                status_md = f"**{run.benchmark_name}** — {run.status}  ({current}/{total})"
                active_task = run.benchmark_name

                results = run.results  # already loaded via joinedload
                if results:
                    n = len(results)
                    ok = sum(1 for r in results if r.correct)
                    tps_vals = [r.tps for r in results if r.tps and r.tps > 0]
                    ttft_vals = [r.ttft for r in results if r.ttft and r.ttft > 0]
                    avg_tps = round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0.0
                    avg_ttft = round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0.0
                    accuracy = f"{round(ok/n*100, 1) if n else 0}%"
                    total_tk = sum((r.thinking_tokens or 0) + (r.response_tokens or 0) for r in results)
                    think_tk = sum(r.thinking_tokens or 0 for r in results)
                    resp_tk = sum(r.response_tokens or 0 for r in results)
                    think_pct = round(think_tk / total_tk * 100, 1) if total_tk else 0.0
                    resp_pct = round(resp_tk / total_tk * 100, 1) if total_tk else 0.0
                    token_stats = f"🧠 {think_pct}% | 💬 {resp_pct}% | Σ {total_tk}"
        finally:
            db.close()

    batch_prog_val = 0.0
    batch_status_md = ""
    batch_eta_str = ""
    batch_summary_df = pd.DataFrame()
    batch_id_val = ""
    batch_done = 0
    batch_total = 0
    batch_current_name = ""

    with _batch_lock:
        bid = _active_batch_id

    if bid:
        batch_id_val = bid
        db = SessionLocal()
        try:
            runs = db.query(Run).filter(Run.batch_id == bid).order_by(Run.id).all()
            if runs:
                batch_total = len(runs)
                batch_done = sum(1 for r in runs if r.status in ("COMPLETED", "FAILED", "HALTED"))
                batch_prog_val = batch_done / batch_total if batch_total > 0 else 0
                running_names = [r.benchmark_name for r in runs if r.status == "RUNNING"]
                batch_current_name = running_names[0] if running_names else (runs[-1].benchmark_name if runs else "")
                batch_status_md = f"Batch: {batch_done}/{batch_total} — Current: {batch_current_name}"

                if _batch_start_time and batch_done > 0:
                    total_done_samples = sum(r.current_index or 0 for r in runs if r.status in ("COMPLETED", "FAILED"))
                    total_remaining = sum((r.total_samples or 1) - (r.current_index or 0) for r in runs if r.status not in ("COMPLETED", "FAILED"))
                    if total_done_samples > 0 and total_remaining > 0:
                        elapsed = time.time() - (_batch_start_time or time.time())
                        avg = elapsed / total_done_samples
                        est = int(avg * total_remaining)
                        batch_eta_str = f"{est // 60}m{est % 60}s" if est > 60 else f"~{est}s"

                batch_summary_df = _build_batch_summary(bid)
        finally:
            db.close()

    # If the active run is done but the batch is still running, show the
    # currently RUNNING run's data so live progress stays current.
    active_run_override: int | None = None
    if active_run_id and bid:
        db3 = SessionLocal()
        try:
            orig_run = db3.query(Run).filter(Run.id == active_run_id).first()
            if orig_run and orig_run.status in ("COMPLETED", "FAILED", "HALTED"):
                running = db3.query(Run).options(joinedload(Run.results)).filter(
                    Run.batch_id == bid, Run.status == "RUNNING"
                ).order_by(Run.id).first()
                if running:
                    total = running.total_samples or 1
                    current = running.current_index or 0
                    prog_val = min(current / total, 1.0)
                    status_md = f"**{running.benchmark_name}** — {running.status}  ({current}/{total})"
                    active_task = running.benchmark_name
                    results = running.results
                    if results:
                        n = len(results)
                        ok = sum(1 for r in results if r.correct)
                        tps_vals = [r.tps for r in results if r.tps and r.tps > 0]
                        ttft_vals = [r.ttft for r in results if r.ttft and r.ttft > 0]
                        avg_tps = round(sum(tps_vals) / len(tps_vals), 1) if tps_vals else 0.0
                        avg_ttft = round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0.0
                        accuracy = f"{round(ok/n*100, 1) if n else 0}%"
                        total_tk = sum((r.thinking_tokens or 0) + (r.response_tokens or 0) for r in results)
                        think_tk = sum(r.thinking_tokens or 0 for r in results)
                        resp_tk = sum(r.response_tokens or 0 for r in results)
                        think_pct = round(think_tk / total_tk * 100, 1) if total_tk else 0.0
                        resp_pct = round(resp_tk / total_tk * 100, 1) if total_tk else 0.0
                        token_stats = f"🧠 {think_pct}% | 💬 {resp_pct}% | Σ {total_tk}"
                    active_run_override = running.id
        finally:
            db3.close()

    now = time.time()
    if now - _history_cache["timestamp"] > _CACHE_TTL:
        _history_cache["data"] = load_history()
        _history_cache["timestamp"] = now
    history_df = _history_cache["data"]
    if now - _recent_runs_cache["timestamp"] > _CACHE_TTL:
        _recent_runs_cache["data"] = load_recent_runs()
        _recent_runs_cache["timestamp"] = now
    recent_runs_list = _recent_runs_cache["data"]

    return (
        cpu_text, ram_text, gpu_text, vram_text,
        cpu_df, ram_df, gpu_df, vram_df,
        prog_val, status_md, active_task,
        avg_tps, avg_ttft, accuracy,
        token_stats,
        batch_prog_val, batch_status_md, batch_eta_str,
        batch_summary_df,
        new_smooth_cpu, new_smooth_gpu,
        history_df, recent_runs_list,
        batch_id_val, batch_done, batch_total, batch_current_name,
        active_run_override,
    )


def get_stats() -> dict:
    db = SessionLocal()
    try:
        runs = db.query(Run).options(joinedload(Run.results)).all()
        total_runs = len(runs)
        completed_runs = sum(1 for r in runs if r.status == "COMPLETED")

        total_tokens = 0
        benchmarks = set()
        models = set()
        best_acc = 0.0
        best_model = "—"
        best_bench = "—"

        for r in runs:
            benchmarks.add(r.benchmark_name)
            models.add(r.model_name)
            results = r.results
            n = len(results)
            if n:
                total_tokens += sum((res.thinking_tokens or 0) + (res.response_tokens or 0) for res in results)
                if r.status in ("COMPLETED", "FAILED", "HALTED"):
                    ok = sum(1 for res in results if res.correct)
                    acc = (ok / n * 100)
                    if acc > best_acc:
                        best_acc = round(acc, 1)
                        best_model = r.model_name
                        best_bench = r.benchmark_name

        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "total_tokens_generated": total_tokens,
            "benchmarks_run": sorted(list(benchmarks)),
            "models_tested": sorted(list(models)),
            "best_accuracy": {
                "model": best_model,
                "benchmark": best_bench,
                "accuracy": best_acc
            }
        }
    except Exception as e:
        logger.error(f"get_stats error: {e}", exc_info=True)
        return {
            "total_runs": 0,
            "completed_runs": 0,
            "total_tokens_generated": 0,
            "benchmarks_run": [],
            "models_tested": [],
            "best_accuracy": {"model": "—", "benchmark": "—", "accuracy": 0.0}
        }
    finally:
        db.close()
