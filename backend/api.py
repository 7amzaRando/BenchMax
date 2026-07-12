import json, logging, time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from backend.database import SessionLocal, Run, Result
from backend.operations import (
    connect_lm_studio, trigger_run, start_batch, pause_run, resume_run, halt_run,
    load_history, load_run_details, load_batch_summary, analyze_run,
    load_recent_runs, load_leaderboard, delete_leaderboard_entry,
    clear_all_history, load_cross_comparison, export_results, export_batch_results,
    export_telemetry, export_all_history, generate_diff,
    _scan_datasets, install_dataset, install_all_missing,
    update_context_window, update_ctx_warning,
    _load_hf_token, _save_hf_token,
    save_lb_api_key, load_lb_settings, sync_to_online_leaderboard,
    poll, get_batch_start_time, get_active_batch_id,
    start_model_queue, get_model_queue_state, halt_model_queue, skip_current_model,
    get_stats, download_runtimes,
)
from backend import operations
from backend.config import BENCHMARKS, BENCH_NAMES, PROVIDER_PRESETS, DATASETS, ROOT
from backend.telemetry.monitor import get_system_metrics

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectRequest(BaseModel):
    api_url: str
    api_key: str = ""

class RunRequest(BaseModel):
    model: str
    benchmark: str
    api_url: str
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = True

class BatchRequest(BaseModel):
    model: str
    benchmarks: list[str]
    api_url: str
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = True

class ModelQueueRequest(BaseModel):
    models: list[str]
    benchmarks: list[str]
    api_url: str
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = True

class ResumeRequest(BaseModel):
    api_url: str
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = True

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
    return json.loads(df.to_json(orient="records"))

@router.post("/connect")
def api_connect(req: ConnectRequest):
    """Connect to an LM Studio instance and list available models."""
    try:
        status_str, models_df, model_choices, metadata = connect_lm_studio(req.api_url, req.api_key)
        models = _df_to_dict(models_df)
        choices = model_choices if isinstance(model_choices, list) else []
        selected = choices[0] if choices else None
        return {
            "status": status_str,
            "models": models,
            "choices": choices,
            "selected": selected,
            "metadata": metadata,
        }
    except Exception as e:
        logger.error(f"api_connect failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connect/metadata")
def api_get_metadata():
    """Return available providers, benchmarks, and benchmark names for the UI connection tab."""
    return {
        "providers": PROVIDER_PRESETS,
        "benchmarks": BENCHMARKS,
        "bench_names": BENCH_NAMES,
    }

@router.get("/datasets")
def api_scan_datasets():
    """Scan the data/ directory and report which datasets are installed."""
    try:
        df = _scan_datasets()
        return {"datasets": _df_to_dict(df)}
    except Exception as e:
        logger.error(f"api_scan_datasets failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/datasets/install/{bench_name}")
def api_install_dataset(bench_name: str, req: InstallRequest = Body(default=InstallRequest())):
    """Download and install the full dataset for a given benchmark."""
    try:
        status = install_dataset(bench_name, req.hf_token)
        return {"status": status}
    except Exception as e:
        logger.error(f"api_install_dataset({bench_name}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/datasets/install-all")
def api_install_all(req: InstallRequest = Body(default=InstallRequest())):
    """Install all missing datasets at once."""
    try:
        result = install_all_missing(req.hf_token)
        return {"status": result}
    except Exception as e:
        logger.error(f"api_install_all failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hf-token")
def api_get_hf_token():
    """Return the stored HuggingFace API token (masked for UI display)."""
    token = _load_hf_token()
    masked = token[:4] + "****" + token[-4:] if len(token) > 8 else "****" if token else ""
    return {"token": masked}

@router.post("/hf-token")
def api_set_hf_token(req: HfTokenRequest):
    """Save a HuggingFace API token for dataset downloads."""
    return {"status": _save_hf_token(req.token)}

@router.post("/run/start")
def api_trigger_run(req: RunRequest):
    """Start a single benchmark run with the given model and parameters."""
    try:
        run_id, msg = trigger_run(
            req.model, req.benchmark, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
        )
        return {"run_id": run_id, "message": msg}
    except Exception as e:
        logger.error(f"api_trigger_run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch/start")
def api_start_batch(req: BatchRequest):
    """Start a batch of benchmarks (multiple benchmarks, single model)."""
    try:
        first_run_id, batch_id, msg, summary_df, batch_id_display = start_batch(
            req.model, req.benchmarks, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
        )
        return {
            "run_id": first_run_id,
            "batch_id": batch_id,
            "message": msg,
            "summary": _df_to_dict(summary_df),
            "batch_id_display": batch_id_display,
        }
    except Exception as e:
        logger.error(f"api_start_batch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/model-queue/start")
def api_start_model_queue(req: ModelQueueRequest):
    """Start a model queue run (multiple models, multiple benchmarks, sequential)."""
    try:
        model_benchmarks = [(m, req.benchmarks) for m in req.models]
        queue_id, msg = start_model_queue(
            model_benchmarks, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
        )
        return {"queue_id": queue_id, "message": msg}
    except Exception as e:
        logger.error(f"api_start_model_queue failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/model-queue/active")
def api_active_model_queue():
    """Get the current state of the model queue (if active)."""
    try:
        state = get_model_queue_state()
        return state
    except Exception as e:
        logger.error(f"api_active_model_queue failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/model-queue/halt")
def api_halt_model_queue():
    """Halt the currently running model queue and unload the active model."""
    try:
        status = halt_model_queue()
        return {"status": status}
    except Exception as e:
        logger.error(f"api_halt_model_queue failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/model-queue/skip")
def api_skip_model_queue():
    """Skip the currently running model and advance to the next in the queue."""
    try:
        status = skip_current_model()
        return {"status": status}
    except Exception as e:
        logger.error(f"api_skip_model_queue failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run/{run_id}/pause")
def api_pause_run(run_id: int):
    """Pause an active benchmark run. Can be resumed later."""
    try:
        status = pause_run(run_id)
        return {"status": status}
    except Exception as e:
        logger.error(f"api_pause_run({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run/{run_id}/resume")
def api_resume_run(run_id: int, req: ResumeRequest):
    """Resume a previously paused benchmark run."""
    try:
        status = resume_run(run_id, req.api_url, req.api_key, req.temperature, req.max_tokens, req.system_prompt, req.quick_test)
        return {"status": status}
    except Exception as e:
        logger.error(f"api_resume_run({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run/{run_id}/halt")
def api_halt_run(run_id: int):
    """Halt (terminate) a benchmark run. Cannot be resumed."""
    try:
        status = halt_run(run_id)
        return {"status": status}
    except Exception as e:
        logger.error(f"api_halt_run({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/run/{run_id}/status")
def api_run_status(run_id: int):
    """Get live status and aggregated metrics for a benchmark run."""
    try:
        db = SessionLocal()
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                return {"error": "Run not found"}
            results = db.query(Result).filter(Result.run_id == run_id).all()
            n = len(results)
            ok = sum(1 for r in results if r.correct)
            tps_vals = [r.tps for r in results if r.tps and r.tps > 0]
            ttft_vals = [r.ttft for r in results if r.ttft and r.ttft > 0]
            total_tk = sum((r.thinking_tokens or 0) + (r.response_tokens or 0) for r in results)
            think_tk = sum(r.thinking_tokens or 0 for r in results)
            resp_tk = sum(r.response_tokens or 0 for r in results)
            rep_warnings = [r.error_message or "" for r in results if "Repetition" in (r.error_message or "")]
            safety_metrics = None
            if run.benchmark_name == "Safety":
                params_dict = run.get_parameters()
                safety_metrics = params_dict.get("_safety_metrics")
            return {
                "run_id": run.id,
                "model_name": run.model_name,
                "benchmark_name": run.benchmark_name,
                "status": run.status,
                "current_index": run.current_index,
                "total_samples": run.total_samples,
                "samples_completed": n,
                "samples_correct": ok,
                "accuracy": round(ok / n * 100, 1) if n else 0,
                "accuracy_display": f"{round(ok/n*100, 1)}%" if n else "0%",
                "avg_tps": round(sum(tps_vals) / len(tps_vals), 2) if tps_vals else 0,
                "avg_ttft": round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0,
                "total_tokens": total_tk,
                "thinking_tokens": think_tk,
                "response_tokens": resp_tk,
                "repetition_warnings": len(rep_warnings),
                "safety_metrics": safety_metrics,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"api_run_status({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs")
def api_load_history():
    """Load the full history of all completed/in-progress runs."""
    try:
        df = load_history()
        return {"runs": _df_to_dict(df)}
    except Exception as e:
        logger.error(f"api_load_history failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}")
def api_load_run_details(run_id: int):
    """Load detailed results, token charts, and histograms for a single run."""
    try:
        summary, samples_df, failed_choices, token_df, ttft_hist, tps_hist, cat_chart = load_run_details(str(run_id))
        return {
            "summary": summary,
            "samples": _df_to_dict(samples_df),
            "failed_tasks": failed_choices if isinstance(failed_choices, list) else [],
            "selected_failed": failed_choices[0] if (isinstance(failed_choices, list) and failed_choices) else None,
            "token_chart": _df_to_dict(token_df),
            "ttft_histogram": _df_to_dict(ttft_hist),
            "tps_histogram": _df_to_dict(tps_hist),
            "category_chart": _df_to_dict(cat_chart),
        }
    except Exception as e:
        logger.error(f"api_load_run_details({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}/diff/{task_id:path}")
def api_generate_diff(run_id: int, task_id: str):
    """Generate a unified diff between the expected answer and model output for a specific task."""
    try:
        html = generate_diff(str(run_id), task_id)
        return {"html": html}
    except Exception as e:
        logger.error(f"api_generate_diff({run_id}, {task_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent-runs")
def api_recent_runs():
    """Return a list of the most recent run IDs for the dropdown selector."""
    try:
        choices = load_recent_runs()
        return {"runs": choices if isinstance(choices, list) else []}
    except Exception as e:
        logger.error(f"api_recent_runs failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analyze/{run_id}")
def api_analyze_run(run_id: int):
    """Analyze a completed run with summary, charts, and per-sample breakdown."""
    try:
        summary, samples_df, failed_choices, token_df, ttft_hist, tps_hist, cat_chart = analyze_run(str(run_id))
        return {
            "summary": summary,
            "samples": _df_to_dict(samples_df),
            "failed_tasks": failed_choices if isinstance(failed_choices, list) else [],
            "token_chart": _df_to_dict(token_df),
            "ttft_histogram": _df_to_dict(ttft_hist),
            "tps_histogram": _df_to_dict(tps_hist),
            "category_chart": _df_to_dict(cat_chart),
        }
    except Exception as e:
        logger.error(f"api_analyze_run({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batch/active")
def api_active_batch():
    """Get progress of the currently active batch run."""
    batch_id_val = get_active_batch_id()
    if not batch_id_val:
        return {"batch_id": None, "active": False}
    db = SessionLocal()
    try:
        runs = db.query(Run).filter(Run.batch_id == batch_id_val).order_by(Run.id).all()
        completed = sum(1 for r in runs if r.status in ("COMPLETED", "FAILED"))
        total = len(runs)
        current = None
        for br in runs:
            if br.status == "RUNNING":
                current = br.benchmark_name
                break
        eta = ""
        bst = get_batch_start_time()
        if bst and completed > 0:
            total_done = sum(br.total_samples or 1 for br in runs if br.status in ("COMPLETED", "FAILED"))
            total_remaining = sum((br.total_samples or 1) - (br.current_index or 0) for br in runs if br.status not in ("COMPLETED", "FAILED"))
            if total_done > 0 and total_remaining > 0:
                elapsed = time.time() - bst
                avg = elapsed / total_done
                est = int(avg * total_remaining)
                eta = f"{est // 60}m{est % 60}s" if est > 60 else f"~{est}s"
        return {
            "batch_id": batch_id_val,
            "active": True,
            "completed": completed,
            "total": total,
            "current_benchmark": current,
            "eta": eta,
            "progress": completed / total if total > 0 else 0,
        }
    finally:
        db.close()

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
    except Exception as e:
        logger.error(f"api_batch_summary({batch_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/runs/{run_id}")
def api_export_results(run_id: int, export_format: str = Query("CSV", alias="format")):
    """Export a single run's results as CSV or JSON file download."""
    try:
        file_path, status = export_results(str(run_id), export_format)
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        logger.error(f"api_export_results({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/batch/{batch_id}")
def api_export_batch(batch_id: str, export_format: str = Query("CSV", alias="format")):
    """Export results for an entire batch as CSV or JSON file download."""
    try:
        file_path, status = export_batch_results(batch_id, export_format)
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        logger.error(f"api_export_batch({batch_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/telemetry")
def api_export_telemetry():
    """Export telemetry history as a CSV file download."""
    try:
        file_path, status = export_telemetry()
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        logger.error(f"api_export_telemetry failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/history")
def api_export_history():
    """Export all run history as a CSV file download."""
    try:
        file_path, status = export_all_history()
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        logger.error(f"api_export_history failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        logger.error(f"api_comparison failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leaderboard")
def api_leaderboard():
    """Get the local leaderboard with all completed runs."""
    try:
        df = load_leaderboard()
        return {"leaderboard": _df_to_dict(df)}
    except Exception as e:
        logger.error(f"api_leaderboard failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/leaderboard/{run_id}")
def api_delete_leaderboard(run_id: int):
    """Delete a single entry from the leaderboard by run ID."""
    try:
        lb_df, status = delete_leaderboard_entry(str(run_id))
        return {"leaderboard": _df_to_dict(lb_df), "status": status}
    except Exception as e:
        logger.error(f"api_delete_leaderboard({run_id}) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        logger.error(f"api_clear_leaderboard failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leaderboard/settings")
def api_lb_settings():
    """Get the stored online leaderboard sync API key."""
    return {"api_key": load_lb_settings()}

@router.post("/leaderboard/settings")
def api_save_lb_settings(req: ApiKeyRequest):
    """Save the online leaderboard sync API key."""
    return {"status": save_lb_api_key(req.api_key)}

@router.post("/leaderboard/sync")
def api_sync_leaderboard(req: ApiKeyRequest = Body(default=ApiKeyRequest(api_key=""))):
    """Sync the local leaderboard to the configured online endpoint."""
    try:
        status = sync_to_online_leaderboard(1, api_key=req.api_key)
        return {"status": status}
    except Exception as e:
        logger.error(f"api_sync_leaderboard failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/telemetry")
def api_telemetry():
    """Get the latest system telemetry snapshot (CPU, RAM, GPU, VRAM)."""
    try:
        metrics = get_system_metrics()
        return metrics
    except Exception as e:
        logger.error(f"api_telemetry failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/telemetry/history")
def api_telemetry_history():
    """Return the last 100 telemetry history entries for chart display."""
    return {"history": operations.telemetry_history[-100:]}

@router.get("/poll")
def api_poll(active_run_id: int = Query(default=0)):
    """Combined polling endpoint: returns telemetry, run progress, and batch progress in one call."""
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
        }
    except Exception as e:
        logger.error(f"Poll error: {e}", exc_info=True)
        return {"error": "Internal error"}

@router.get("/context-window")
def api_context_window(model_id: str = Query(""), metadata: str = Query("{}")):
    """Get the context window size for a given model from LM Studio metadata."""
    try:
        meta = json.loads(metadata) if metadata else {}
        result = update_context_window(model_id, meta)
        value = result if isinstance(result, str) else result.get("value", "N/A") if isinstance(result, dict) else "N/A"
        return {"value": value}
    except Exception as e:
        logger.error(f"api_context_window failed: {e}", exc_info=True)
        return {"value": "N/A", "error": "Internal error"}

@router.get("/context-warning")
def api_context_warning(model_id: str = Query(""), max_tokens: int = Query(2048), metadata: str = Query("{}")):
    """Check if the requested max_tokens exceeds the model's context window and return a warning."""
    try:
        meta = json.loads(metadata) if metadata else {}
        warning = update_ctx_warning(model_id, max_tokens, meta)
        return {"warning": warning}
    except Exception as e:
        logger.error(f"api_context_warning failed: {e}", exc_info=True)
        return {"warning": "", "error": "Internal error"}

@router.get("/providers")
def api_providers():
    """Return the list of built-in provider presets (URLs and API key requirements)."""
    return {"providers": PROVIDER_PRESETS}

@router.get("/benchmarks")
def api_benchmarks():
    """Return the list of all available benchmarks with display labels and internal names."""
    benchmarks = [{"label": b[0], "name": b[1]} for b in BENCHMARKS]
    return {"benchmarks": benchmarks}

@router.post("/runtimes/download")
def api_download_runtimes():
    """Download portable runtimes (Go, Rust, GCC, Java, Node) for Aider Polyglot benchmarks."""
    try:
        status = download_runtimes()
        return {"status": status}
    except Exception as e:
        logger.error(f"api_download_runtimes failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def api_get_stats():
    """Return aggregate statistics: total runs, tokens, models tested, best accuracy."""
    try:
        return get_stats()
    except Exception as e:
        logger.error(f"api_get_stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
