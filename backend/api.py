import asyncio, json, logging, math
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import load_only

from backend.database import Run, Result, get_db

_EXPORT_MIME = {
    "CSV": "text/csv",
    "JSON": "application/json",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
from backend.telemetry.monitor import get_system_metrics
from backend.operations import (
    connect_lm_studio, trigger_run, start_batch, pause_run, resume_run, halt_run,
    load_history, load_run_details, load_batch_summary,
    load_leaderboard, delete_leaderboard_entry,
    clear_all_history, load_cross_comparison, export_results, export_batch_results,
    export_all_history, generate_diff,
    export_leaderboard, export_comparison, export_run_markdown,
    export_all_history_markdown,
    _scan_datasets, install_dataset, install_all_missing,
    _load_hf_token, _save_hf_token,
    save_lb_api_key, load_lb_settings, sync_to_online_leaderboard,
    _compute_result_stats,
    poll,
    start_model_queue, get_model_queue_state, halt_model_queue, skip_current_model,
    check_benchmark_readiness,
    build_docker_image, get_docker_status,
)
from backend.config import BENCHMARKS, BENCH_NAMES, PROVIDER_PRESETS, DATASETS
logger = logging.getLogger(__name__)


def sanitize_for_json(obj):
    """Recursively replace non-JSON-compliant floats (NaN/Inf) with 0.0.

    Starlette's JSONResponse renders with allow_nan=False, so a single NaN
    anywhere in a response dict crashes the request with
    "ValueError: Out of range float values are not JSON compliant".
    Sources are transient and hard to trace (external telemetry counters,
    LM Studio metadata passthrough), so every JSON response is sanitized
    at the render boundary instead of auditing 40+ endpoints.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return 0.0
    return obj


class SafeJSONResponse(JSONResponse):
    """JSONResponse that can never crash on NaN/Inf payloads."""

    def render(self, content) -> bytes:
        return super().render(sanitize_for_json(content))


router = APIRouter(default_response_class=SafeJSONResponse)

class ConnectRequest(BaseModel):
    api_url: str
    api_key: str = ""

class BaseRunParams(BaseModel):
    api_url: str = ""
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = False
    disable_repetition_detection: bool = False
    context_length: Optional[int] = None

class RunRequest(BaseRunParams):
    model: str
    benchmark: str

class BatchRequest(BaseRunParams):
    model: str
    benchmarks: list[str]

class ModelQueueRequest(BaseRunParams):
    models: list[str]
    benchmarks: list[str]

class ResumeRequest(BaseRunParams):
    api_url: str = ""
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: str = ""
    quick_test: Optional[bool] = None
    disable_repetition_detection: Optional[bool] = None
    context_length: Optional[int] = None

class ConfirmClear(BaseModel):
    confirm_text: str

class ApiKeyRequest(BaseModel):
    api_key: str

class HfTokenRequest(BaseModel):
    token: str = ""

class InstallRequest(BaseModel):
    hf_token: str = ""

def _df_to_dict(df):
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def _handle_api_error(msg: str):
    # Log the full traceback server-side; return a generic detail so raw
    # exception text (paths, API key fragments) never leaks to the client.
    logger.error(msg, exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/connect")
async def api_connect(req: ConnectRequest):
    """Connect to an LM Studio instance and list available models."""
    try:
        status_str, models_df, model_choices, metadata = await connect_lm_studio(req.api_url, req.api_key)
        models = _df_to_dict(models_df)
        choices = model_choices if isinstance(model_choices, list) else []
        selected = choices[0] if choices else None
        # metadata/models come straight from LM Studio's JSON — sanitize
        # external floats (NaN context lengths etc.) before returning.
        return sanitize_for_json({
            "status": status_str,
            "models": models,
            "choices": choices,
            "selected": selected,
            "metadata": metadata,
        })
    except Exception:
        _handle_api_error("api_connect failed")

@router.get("/datasets")
def api_scan_datasets():
    """Scan the data/ directory and report which datasets are installed."""
    try:
        df = _scan_datasets()
        return {"datasets": _df_to_dict(df)}
    except Exception:
        _handle_api_error("api_scan_datasets failed")

@router.post("/datasets/install/{bench_name}")
async def api_install_dataset(bench_name: str, req: InstallRequest = Body(default=InstallRequest())):
    """Download and install the full dataset for a given benchmark."""
    try:
        status = await install_dataset(bench_name, req.hf_token)
        return {"status": status}
    except Exception:
        _handle_api_error(f"api_install_dataset({bench_name}) failed")

@router.post("/datasets/install-all")
async def api_install_all(req: InstallRequest = Body(default=InstallRequest())):
    """Install all missing datasets at once."""
    try:
        result = await install_all_missing(req.hf_token)
        return {"status": result}
    except Exception:
        _handle_api_error("api_install_all failed")

@router.get("/hf-token")
def api_get_hf_token():
    """Return the stored HuggingFace API token (masked for UI display)."""
    try:
        token = _load_hf_token()
        masked = token[:4] + "****" + token[-4:] if len(token) > 8 else "****" if token else ""
        return {"token": masked}
    except Exception:
        _handle_api_error("api_get_hf_token failed")

@router.post("/hf-token")
def api_set_hf_token(req: HfTokenRequest):
    """Save a HuggingFace API token for dataset downloads."""
    try:
        return {"status": _save_hf_token(req.token)}
    except Exception:
        _handle_api_error("api_set_hf_token failed")

@router.post("/run/start")
def api_trigger_run(req: RunRequest):
    """Start a single benchmark run with the given model and parameters.

    Args:
        req: RunRequest with model, benchmark, and optional temperature/max_tokens/system_prompt.

    Returns:
        dict: {"run_id": int, "message": str} on success.

    Raises:
        HTTPException: 500 if the run cannot be started.
    """
    try:
        run_id, msg = trigger_run(
            req.model, req.benchmark, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
            req.disable_repetition_detection, req.context_length,
        )
        return {"run_id": run_id, "message": msg}
    except Exception:
        _handle_api_error("api_trigger_run failed")

@router.post("/batch/start")
def api_start_batch(req: BatchRequest):
    """Start a batch of benchmarks (multiple benchmarks, single model)."""
    try:
        first_run_id, batch_id, msg, summary_df, batch_id_display = start_batch(
            req.model, req.benchmarks, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
            req.disable_repetition_detection, req.context_length,
        )
        return {
            "run_id": first_run_id,
            "batch_id": batch_id,
            "message": msg,
            "summary": _df_to_dict(summary_df),
            "batch_id_display": batch_id_display,
        }
    except Exception:
        _handle_api_error("api_start_batch failed")

@router.post("/model-queue/start")
def api_start_model_queue(req: ModelQueueRequest):
    """Start a model queue run (multiple models, multiple benchmarks, sequential)."""
    try:
        model_benchmarks = [(m, req.benchmarks) for m in req.models]
        queue_id, msg = start_model_queue(
            model_benchmarks, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
            req.disable_repetition_detection, req.context_length,
        )
        return {"queue_id": queue_id, "message": msg}
    except Exception:
        _handle_api_error("api_start_model_queue failed")

class RunCheckRequest(BaseRunParams):
    benchmarks: list[str]

@router.post("/run/check")
def api_check_run_readiness(req: RunCheckRequest):
    """Check whether the selected benchmark(s) are ready to run (datasets/runtime installed)."""
    try:
        issues = []
        for bn in req.benchmarks:
            issues.extend(check_benchmark_readiness(bn, req.quick_test))
        return {"ok": len(issues) == 0, "issues": issues}
    except Exception:
        _handle_api_error("api_check_run_readiness failed")

@router.get("/model-queue/active")
def api_active_model_queue():
    """Get the current state of the model queue (if active)."""
    try:
        state = get_model_queue_state()
        return state
    except Exception:
        _handle_api_error("api_active_model_queue failed")

@router.post("/model-queue/halt")
def api_halt_model_queue():
    """Halt the currently running model queue and unload the active model."""
    try:
        status = halt_model_queue()
        return {"status": status}
    except Exception:
        _handle_api_error("api_halt_model_queue failed")

@router.post("/model-queue/skip")
def api_skip_model_queue():
    """Skip the currently running model and advance to the next in the queue."""
    try:
        status = skip_current_model()
        return {"status": status}
    except Exception:
        _handle_api_error("api_skip_model_queue failed")

@router.post("/run/{run_id}/pause")
def api_pause_run(run_id: int):
    """Pause an active benchmark run. Can be resumed later."""
    try:
        status = pause_run(run_id)
        return {"status": status}
    except Exception:
        _handle_api_error(f"api_pause_run({run_id}) failed")

@router.post("/run/{run_id}/resume")
def api_resume_run(run_id: int, req: ResumeRequest):
    """Resume a paused/halted/failed (or shutdown-interrupted) benchmark run from its saved position. Uses the run's stored settings when present."""
    try:
        status = resume_run(run_id, req.api_url, req.api_key, req.temperature, req.max_tokens, req.system_prompt, req.quick_test, req.disable_repetition_detection, req.context_length)
        return {"status": status}
    except Exception:
        _handle_api_error(f"api_resume_run({run_id}) failed")

@router.post("/run/{run_id}/halt")
def api_halt_run(run_id: int):
    """Halt (terminate) a benchmark run. Cannot be resumed."""
    try:
        status = halt_run(run_id)
        return {"status": status}
    except Exception:
        _handle_api_error(f"api_halt_run({run_id}) failed")

@router.get("/run/{run_id}/status")
def api_run_status(run_id: int):
    """Get live status and aggregated metrics for a benchmark run.

    Args:
        run_id: The run's primary key.

    Returns:
        dict: run_id, model_name, benchmark_name, status, current_index,
              total_samples, avg_tps, avg_ttft, accuracy, token stats, etc.
    """
    try:
        with get_db() as db:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            results = db.query(Result).options(
                load_only(
                    Result.correct, Result.tps, Result.ttft,
                    Result.thinking_tokens, Result.response_tokens, Result.prompt_tokens,
                    Result.error_message,
                )
            ).filter(Result.run_id == run_id).all()
            stats = _compute_result_stats(results)
            rep_warnings = [r.error_message or "" for r in results if "Repetition" in (r.error_message or "")]
            safety_metrics = None
            if run.benchmark_name == "UncensorBench":
                params_dict = run.get_parameters()
                safety_metrics = params_dict.get("_safety_metrics")
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
    except HTTPException:
        raise
    except Exception:
        _handle_api_error(f"api_run_status({run_id}) failed")

@router.get("/runs")
def api_load_history(offset: int = Query(0, ge=0), limit: int = Query(0, ge=0)):
    """Load the full history of all completed/in-progress runs."""
    try:
        df, total = load_history(offset=offset, limit=limit)
        return {"runs": _df_to_dict(df), "total": total, "offset": offset, "limit": limit}
    except Exception:
        _handle_api_error("api_load_history failed")

@router.get("/runs/{run_id}")
def api_load_run_details(run_id: int):
    """Load detailed results, token charts, and histograms for a single run."""
    try:
        summary, samples_df, failed_choices, token_df, ttft_hist, tps_hist, cat_chart = load_run_details(str(run_id))
        benchmark_name = ""
        context_length = None
        try:
            with get_db() as db:
                run = db.query(Run).filter(Run.id == run_id).first()
                if run:
                    benchmark_name = run.benchmark_name or ""
                    params = run.get_parameters()
                    context_length = params.get("context_length")
                    if context_length is None and benchmark_name == "NIAHS":
                        context_length = 65536
        except Exception:
            pass
        return {
            "summary": summary,
            "benchmark_name": benchmark_name,
            "context_length": context_length,
            "samples": _df_to_dict(samples_df),
            "failed_tasks": failed_choices if isinstance(failed_choices, list) else [],
            "selected_failed": failed_choices[0] if (isinstance(failed_choices, list) and failed_choices) else None,
            "token_chart": _df_to_dict(token_df),
            "ttft_histogram": _df_to_dict(ttft_hist),
            "tps_histogram": _df_to_dict(tps_hist),
            "category_chart": _df_to_dict(cat_chart),
        }
    except Exception:
        _handle_api_error(f"api_load_run_details({run_id}) failed")

@router.get("/runs/{run_id}/diff/{task_id:path}")
def api_generate_diff(run_id: int, task_id: str):
    """Generate a unified diff between the expected answer and model output for a specific task."""
    try:
        html = generate_diff(str(run_id), task_id)
        return {"html": html}
    except Exception:
        _handle_api_error(f"api_generate_diff({run_id}, {task_id}) failed")

@router.patch("/runs/{run_id}/notes")
def api_update_notes(run_id: int, body: dict = Body(...)):
    """Update the notes field for a run."""
    try:
        with get_db() as db:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            run.notes = body.get("notes", "")
            db.commit()
            return {"status": "ok", "notes": run.notes}
    except HTTPException:
        raise
    except Exception:
        _handle_api_error(f"api_update_notes({run_id}) failed")

@router.get("/runs/{run_id}/depth-results")
def api_depth_results(run_id: int):
    """Get per-sample correctness and depth for NIAHS depth analysis chart.

    Supports both legacy single-needle schema (one depth per Result) and the
    new multi-needle schema (5 depths per Result via per_depth_correct).
    """
    try:
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
                    # Multi-needle: expand one Result into 5 depth points
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
            return {"results": depth_data}
    except Exception:
        _handle_api_error(f"api_depth_results({run_id}) failed")

@router.get("/batch/{batch_id}")
def api_batch_summary(batch_id: str):
    """Get the summary, accuracy chart, and latency chart for a batch."""
    try:
        summary_df, chart_df, latency_df = load_batch_summary(batch_id)
        return {
            "summary": _df_to_dict(summary_df),
            "chart": _df_to_dict(chart_df),
            "latency_chart": _df_to_dict(latency_df),
        }
    except Exception:
        _handle_api_error(f"api_batch_summary({batch_id}) failed")

@router.get("/export/runs/{run_id}")
def api_export_results(run_id: int, export_format: str = Query("CSV", alias="format")):
    """Export a single run's results as CSV, JSON, or Excel file download."""
    try:
        file_path, status = export_results(str(run_id), export_format)
        if file_path:
            mime = _EXPORT_MIME.get(export_format, "application/octet-stream")
            return FileResponse(file_path, filename=Path(file_path).name, media_type=mime)
        return {"status": status, "file": None}
    except Exception:
        _handle_api_error(f"api_export_results({run_id}) failed")

@router.get("/export/batch/{batch_id}")
def api_export_batch(batch_id: str, export_format: str = Query("CSV", alias="format")):
    """Export results for an entire batch as CSV, JSON, or Excel file download."""
    try:
        file_path, status = export_batch_results(batch_id, export_format)
        if file_path:
            mime = _EXPORT_MIME.get(export_format, "application/octet-stream")
            return FileResponse(file_path, filename=Path(file_path).name, media_type=mime)
        return {"status": status, "file": None}
    except Exception:
        _handle_api_error(f"api_export_batch({batch_id}) failed")

@router.get("/export/history")
def api_export_history(export_format: str = Query("CSV", alias="format")):
    """Export all run history as a CSV, JSON, or Excel file download."""
    try:
        file_path, status = export_all_history(export_format)
        if file_path:
            mime = _EXPORT_MIME.get(export_format, "application/octet-stream")
            return FileResponse(file_path, filename=Path(file_path).name, media_type=mime)
        return {"status": status, "file": None}
    except Exception:
        _handle_api_error("api_export_history failed")

@router.get("/export/history/markdown")
def api_export_history_markdown():
    """Export all run history as a Markdown summary table."""
    try:
        file_path, status = export_all_history_markdown()
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="text/markdown")
        return {"status": status, "file": None}
    except Exception:
        _handle_api_error("api_export_history_markdown failed")

@router.get("/export/leaderboard")
def api_export_leaderboard(export_format: str = Query("CSV", alias="format")):
    """Export the leaderboard as CSV, JSON, or Excel file download."""
    try:
        file_path, status = export_leaderboard(export_format)
        if file_path:
            mime = _EXPORT_MIME.get(export_format, "application/octet-stream")
            return FileResponse(file_path, filename=Path(file_path).name, media_type=mime)
        return {"status": status, "file": None}
    except Exception:
        _handle_api_error("api_export_leaderboard failed")

@router.get("/export/comparison")
def api_export_comparison(run_ids: str = Query(""), export_format: str = Query("CSV", alias="format")):
    """Export cross-run comparison as CSV, JSON, or Excel file download."""
    try:
        file_path, status = export_comparison(run_ids, export_format)
        if file_path:
            mime = _EXPORT_MIME.get(export_format, "application/octet-stream")
            return FileResponse(file_path, filename=Path(file_path).name, media_type=mime)
        return {"status": status, "file": None}
    except Exception:
        _handle_api_error("api_export_comparison failed")

@router.get("/export/runs/{run_id}/markdown")
def api_export_run_markdown(run_id: int):
    """Export a single run as a Markdown report."""
    try:
        file_path, status = export_run_markdown(str(run_id))
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="text/markdown")
        return {"status": status, "file": None}
    except Exception:
        _handle_api_error(f"api_export_run_markdown({run_id}) failed")

@router.get("/comparison")
def api_comparison(run_ids: str = Query("")):
    """Compare accuracy, latency, and tokens across multiple runs by comma-separated IDs."""
    try:
        acc_df, latency_df, token_df = load_cross_comparison(run_ids)
        return {
            "accuracy": _df_to_dict(acc_df),
            "latency": _df_to_dict(latency_df),
            "tokens": _df_to_dict(token_df),
        }
    except Exception:
        _handle_api_error("api_comparison failed")

@router.get("/leaderboard")
def api_leaderboard():
    """Get the local leaderboard with all completed runs."""
    try:
        df = load_leaderboard()
        return {"leaderboard": _df_to_dict(df)}
    except Exception:
        _handle_api_error("api_leaderboard failed")

@router.delete("/leaderboard/{run_id}")
def api_delete_leaderboard(run_id: int):
    """Delete a single entry from the leaderboard by run ID."""
    try:
        lb_df, status = delete_leaderboard_entry(str(run_id))
        return {"leaderboard": _df_to_dict(lb_df), "status": status}
    except Exception:
        _handle_api_error(f"api_delete_leaderboard({run_id}) failed")

@router.post("/leaderboard/clear")
def api_clear_leaderboard(req: ConfirmClear):
    """Clear the entire run history and leaderboard (requires confirmation text)."""
    try:
        history_df, lb_df, status = clear_all_history(req.confirm_text)
        return {
            "history": _df_to_dict(history_df),
            "leaderboard": _df_to_dict(lb_df),
            "status": status,
        }
    except Exception:
        _handle_api_error("api_clear_leaderboard failed")

@router.get("/leaderboard/settings")
def api_lb_settings():
    """Get the stored online leaderboard sync API key (masked for UI display)."""
    try:
        key = load_lb_settings()
        masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****" if key else ""
        return {"api_key": masked}
    except Exception:
        _handle_api_error("api_lb_settings failed")

@router.post("/leaderboard/settings")
def api_save_lb_settings(req: ApiKeyRequest):
    """Save the online leaderboard sync API key."""
    try:
        return {"status": save_lb_api_key(req.api_key)}
    except Exception:
        _handle_api_error("api_save_lb_settings failed")

@router.post("/leaderboard/sync")
async def api_sync_leaderboard(req: ApiKeyRequest = Body(default=ApiKeyRequest(api_key=""))):
    """Sync the local leaderboard to the configured online endpoint."""
    try:
        status = await sync_to_online_leaderboard(1, api_key=req.api_key)
        return {"status": status}
    except Exception:
        _handle_api_error("api_sync_leaderboard failed")

@router.get("/telemetry")
def api_telemetry():
    """Get the latest system telemetry snapshot (CPU, RAM, GPU, VRAM). Used by HardwareTab for live monitoring."""
    try:
        metrics = get_system_metrics()
        return metrics
    except Exception:
        _handle_api_error("api_telemetry failed")


@router.get("/poll")
def api_poll(active_run_id: int = Query(default=0)):
    """Combined polling endpoint: returns telemetry, run progress, and batch progress in one call.

    Args:
        active_run_id: ID of the currently active run (0 or omitted for no active run).

    Returns:
        dict: telemetry (cpu/ram/gpu), run_progress (accuracy, tps, ttft, tokens),
              batch_progress (summary, ETA, per-benchmark chart data).
    """
    try:
        result = poll(active_run_id or None)
        metrics = result["metrics"]
        prog_val = result["prog_val"]
        status_md = result["status_md"]
        active_task = result["active_task"]
        avg_tps = result["avg_tps"]
        avg_ttft = result["avg_ttft"]
        accuracy = result["accuracy"]
        token_stats = result["token_stats"]
        batch_prog_val = result["batch_prog_val"]
        batch_status_md = result["batch_status_md"]
        batch_eta_str = result["batch_eta_str"]
        batch_summary_df = result["batch_summary_df"]
        batch_id_val = result["batch_id_val"]
        batch_done = result["batch_done"]
        batch_total = result["batch_total"]
        batch_current_name = result["batch_current_name"]
        active_run_override = result["active_run_override"]
        live_turn = result.get("live_turn")

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
                "progress": prog_val,
                "status_md": status_md,
                "active_task": active_task,
                "avg_tps": avg_tps,
                "avg_ttft": avg_ttft,
                "accuracy": accuracy,
                "token_stats": token_stats,
            },
            "batch_progress": {
                "progress": batch_prog_val,
                "status_md": batch_status_md,
                "eta": batch_eta_str,
                "summary": _df_to_dict(batch_summary_df),
                "batch_id": batch_id_val,
                "completed": batch_done,
                "total": batch_total,
                "current_benchmark": batch_current_name,
            },
            "active_run_override": active_run_override,
            "live_turn": live_turn,
        }
    except Exception:
        logger.error("Poll error", exc_info=True)
        _handle_api_error("api_poll failed")

@router.get("/poll/stream")
async def api_poll_stream(active_run_id: int = Query(default=0)):
    """SSE stream alternative to GET /poll — pushes same JSON every 3s via text/event-stream."""
    import orjson

    async def gen():
        yield "retry: 3000\n\n"
        while True:
            try:
                result = await asyncio.to_thread(poll, active_run_id or None)
                metrics = result["metrics"]
                payload = {
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
                        "summary": _df_to_dict(result["batch_summary_df"]),
                        "batch_id": result["batch_id_val"],
                        "completed": result["batch_done"],
                        "total": result["batch_total"],
                        "current_benchmark": result["batch_current_name"],
                    },
                    "active_run_override": result["active_run_override"],
                    "live_turn": result.get("live_turn"),
                }
                data = orjson.dumps(payload).decode()
                yield f"data: {data}\n\n"
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("poll/stream iteration failed")
                yield 'event: error\ndata: {"error":"poll failed"}\n\n'
            await asyncio.sleep(3)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/benchmarks")
def api_benchmarks():
    """Return the list of all available benchmarks with display labels and internal names."""
    try:
        from backend.config import BENCHMARK_META
        benchmarks = []
        for label, name in BENCHMARKS:
            meta = BENCHMARK_META.get(name, {})
            benchmarks.append({
                "label": label,
                "name": name,
                "category": meta.get("category", "Other"),
                "docker": bool(meta.get("docker")),
                "samples": meta.get("samples", 0),
                "short": meta.get("short", ""),
            })
        return {"benchmarks": benchmarks}
    except Exception:
        _handle_api_error("api_benchmarks failed")

@router.post("/docker/build")
async def api_build_docker():
    """Build the benchmax-sandbox Docker image with all runtimes."""
    try:
        status = await build_docker_image()
        return {"status": status}
    except Exception:
        _handle_api_error("api_build_docker failed")


@router.get("/docker/status")
async def api_docker_status():
    """Check Docker availability and image status."""
    try:
        return await get_docker_status()
    except Exception:
        _handle_api_error("api_docker_status failed")
