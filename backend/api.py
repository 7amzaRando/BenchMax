import json, logging, os, sys, threading, asyncio, time, uuid, hashlib
from pathlib import Path
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Body, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from backend.database import SessionLocal, Run, Result
from backend.operations import (
    connect_lm_studio, trigger_run, start_batch, pause_run, resume_run, halt_run,
    load_history, load_run_details, load_batch_summary, analyze_run,
    load_recent_runs, load_leaderboard, delete_leaderboard_entry,
    clear_all_history, load_cross_comparison, export_results, export_batch_results,
    export_telemetry, export_all_history, generate_diff,
    _build_images, _scan_datasets, install_dataset, install_all_missing,
    update_context_window, update_ctx_warning,
    _load_hf_token, _save_hf_token,
    save_lb_api_key, load_lb_settings, sync_to_online_leaderboard,
    poll, get_batch_start_time, get_active_batch_id, _batch_queue,
    start_model_queue, get_model_queue_state, halt_model_queue, skip_current_model,
    start_build, get_build_state, get_stats,
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
    quantization: str = ""

class BatchRequest(BaseModel):
    model: str
    benchmarks: list[str]
    api_url: str
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = True
    quantization: str = ""

class ModelQueueRequest(BaseModel):
    models: list[str]
    benchmarks: list[str]
    api_url: str
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = True
    quantization: str = ""

class ResumeRequest(BaseModel):
    api_url: str
    api_key: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 2048
    system_prompt: str = ""
    quick_test: bool = True

class ExportFormat(BaseModel):
    format: str = "CSV"

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

def _gr_update(**kwargs):
    return kwargs

@router.post("/connect")
def api_connect(req: ConnectRequest):
    try:
        status_str, models_df, model_choices, metadata, docker_status = connect_lm_studio(req.api_url, req.api_key)
        models = _df_to_dict(models_df)
        choices = model_choices if isinstance(model_choices, list) else []
        selected = choices[0] if choices else None
        return {
            "status": status_str,
            "models": models,
            "choices": choices,
            "selected": selected,
            "metadata": metadata,
            "docker_status": docker_status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connect/metadata")
def api_get_metadata():
    return {
        "providers": PROVIDER_PRESETS,
        "benchmarks": BENCHMARKS,
        "bench_names": BENCH_NAMES,
    }

@router.get("/docker/status")
def api_docker_status():
    from backend.sandbox.docker_executor import DockerExecutor
    ex = DockerExecutor()
    ok = ex.is_available()
    images = ex.get_available_images() if ok else {}
    built = sum(1 for v in images.values() if v)
    return {"available": ok, "images": images, "built_count": built}

@router.post("/docker/build")
def api_build_images():
    try:
        msg = start_build()
        return {"message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/docker/build/stream")
async def api_build_stream(request: Request):
    async def event_generator():
        seen = 0
        while True:
            if await request.is_disconnected():
                break
            state = get_build_state()
            lines = state.get("lines", [])
            new_lines = lines[seen:]
            for l in new_lines:
                evt_type = "log"
                if l.startswith("[OK]") or l.startswith("[SKIP]"):
                    evt_type = "image"
                elif l.startswith("[ERROR]") or l.startswith("[FAIL]"):
                    evt_type = "error"
                elif "exited with code" in l:
                    evt_type = "done"
                yield f"event: {evt_type}\ndata: {json.dumps({'text': l})}\n\n"
                seen += 1
            if not state.get("running"):
                # Yield one more with images summary
                images = state.get("images", {})
                if images:
                    yield f"event: summary\ndata: {json.dumps(images)}\n\n"
                yield f"event: done\ndata: {json.dumps({'text': 'Build complete', 'exit_code': state.get('exit_code')})}\n\n"
                break
            await asyncio.sleep(0.1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/datasets")
def api_scan_datasets():
    try:
        df = _scan_datasets()
        return {"datasets": _df_to_dict(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/datasets/install/{bench_name}")
def api_install_dataset(bench_name: str, req: InstallRequest = Body(default=InstallRequest())):
    try:
        status = install_dataset(bench_name, req.hf_token)
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/datasets/install-all")
def api_install_all(req: InstallRequest = Body(default=InstallRequest())):
    try:
        result = install_all_missing(req.hf_token)
        return {"status": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hf-token")
def api_get_hf_token():
    return {"token": _load_hf_token()}

@router.post("/hf-token")
def api_set_hf_token(req: HfTokenRequest):
    return {"status": _save_hf_token(req.token)}

@router.post("/run/start")
def api_trigger_run(req: RunRequest):
    try:
        run_id, msg = trigger_run(
            req.model, req.benchmark, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
            quantization=req.quantization,
        )
        return {"run_id": run_id, "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch/start")
def api_start_batch(req: BatchRequest):
    try:
        first_run_id, batch_id, msg, summary_df, batch_id_display = start_batch(
            req.model, req.benchmarks, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
            quantization=req.quantization,
        )
        return {
            "run_id": first_run_id,
            "batch_id": batch_id,
            "message": msg,
            "summary": _df_to_dict(summary_df),
            "batch_id_display": batch_id_display,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/model-queue/start")
def api_start_model_queue(req: ModelQueueRequest):
    try:
        model_benchmarks = [(m, req.benchmarks) for m in req.models]
        queue_id, msg = start_model_queue(
            model_benchmarks, req.api_url, req.api_key,
            req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
            quantization=req.quantization,
        )
        return {"queue_id": queue_id, "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/model-queue/active")
def api_active_model_queue():
    try:
        state = get_model_queue_state()
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/model-queue/halt")
def api_halt_model_queue():
    try:
        status = halt_model_queue()
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/model-queue/skip")
def api_skip_model_queue():
    try:
        status = skip_current_model()
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run/{run_id}/pause")
def api_pause_run(run_id: int):
    try:
        status = pause_run(run_id)
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run/{run_id}/resume")
def api_resume_run(run_id: int, req: ResumeRequest):
    try:
        status = resume_run(run_id, req.api_url, req.api_key, req.temperature, req.max_tokens, req.system_prompt, req.quick_test)
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run/{run_id}/halt")
def api_halt_run(run_id: int):
    try:
        status = halt_run(run_id)
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/run/{run_id}/status")
def api_run_status(run_id: int):
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs")
def api_load_history():
    try:
        df = load_history()
        return {"runs": _df_to_dict(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}")
def api_load_run_details(run_id: int):
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}/diff/{task_id:path}")
def api_generate_diff(run_id: int, task_id: str):
    try:
        html = generate_diff(str(run_id), task_id)
        return {"html": html}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent-runs")
def api_recent_runs():
    try:
        choices = load_recent_runs()
        return {"runs": choices if isinstance(choices, list) else []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analyze/{run_id}")
def api_analyze_run(run_id: int):
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batch/active")
def api_active_batch():
    _active_batch_id = get_active_batch_id()
    if not _active_batch_id:
        return {"batch_id": None, "active": False}
    db = SessionLocal()
    try:
        runs = db.query(Run).filter(Run.batch_id == _active_batch_id).order_by(Run.id).all()
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
            "batch_id": _active_batch_id,
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
    try:
        summary_df, chart_df, latency_df = load_batch_summary(batch_id)
        return {
            "summary": _df_to_dict(summary_df),
            "chart": _df_to_dict(chart_df),
            "latency_chart": _df_to_dict(latency_df),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/runs/{run_id}")
def api_export_results(run_id: int, format: str = Query("CSV")):
    try:
        file_path, status = export_results(str(run_id), format)
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/batch/{batch_id}")
def api_export_batch(batch_id: str, format: str = Query("CSV")):
    try:
        file_path, status = export_batch_results(batch_id, format)
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/telemetry")
def api_export_telemetry():
    try:
        file_path, status = export_telemetry()
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/history")
def api_export_history():
    try:
        file_path, status = export_all_history()
        if file_path:
            return FileResponse(file_path, filename=Path(file_path).name, media_type="application/octet-stream")
        return {"status": status, "file": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comparison")
def api_comparison(run_ids: str = Query("")):
    try:
        acc_df, latency_df, token_df = load_cross_comparison(run_ids)
        return {
            "accuracy": _df_to_dict(acc_df),
            "latency": _df_to_dict(latency_df),
            "tokens": _df_to_dict(token_df),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leaderboard")
def api_leaderboard():
    try:
        df = load_leaderboard()
        return {"leaderboard": _df_to_dict(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/leaderboard/{run_id}")
def api_delete_leaderboard(run_id: int):
    try:
        lb_df, status = delete_leaderboard_entry(str(run_id))
        return {"leaderboard": _df_to_dict(lb_df), "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/leaderboard/clear")
def api_clear_leaderboard(req: ConfirmClear):
    try:
        history_df, lb_df, status = clear_all_history(req.confirm_text)
        return {
            "history": _df_to_dict(history_df),
            "leaderboard": _df_to_dict(lb_df),
            "status": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leaderboard/settings")
def api_lb_settings():
    return {"api_key": load_lb_settings()}

@router.post("/leaderboard/settings")
def api_save_lb_settings(req: ApiKeyRequest):
    return {"status": save_lb_api_key(req.api_key)}

@router.post("/leaderboard/sync")
def api_sync_leaderboard(req: ApiKeyRequest = Body(default=ApiKeyRequest(api_key=""))):
    try:
        status = sync_to_online_leaderboard(1, api_key=req.api_key)
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/telemetry")
def api_telemetry():
    try:
        metrics = get_system_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/telemetry/history")
def api_telemetry_history():
    return {"history": operations.telemetry_history[-100:]}

@router.get("/poll")
def api_poll(active_run_id: int = Query(default=0)):
    try:
        (_cpu_str, _ram_str, _gpu_str, _vram_str,
         _cpu_df, _ram_df, _gpu_df, _vram_df,
         prog_val, status_md, active_task,
         avg_tps, avg_ttft, accuracy,
         token_stats,
         batch_prog_val, batch_status_md, batch_eta_str,
         batch_summary_df,
         _new_smooth_cpu, _new_smooth_gpu,
         _history_df, _recent_runs,
         batch_id_val, batch_done, batch_total, batch_current_name,
         active_run_override) = poll(active_run_id or None)

        metrics = get_system_metrics()

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
        logger.error(f"Poll error: {e}")
        return {"error": str(e)}

@router.get("/context-window")
def api_context_window(model_id: str = Query(""), metadata: str = Query("{}")):
    try:
        meta = json.loads(metadata) if metadata else {}
        result = update_context_window(model_id, meta)
        value = result.get("value") if isinstance(result, dict) else (result.value if hasattr(result, "value") else "N/A")
        return {"value": value}
    except Exception as e:
        return {"value": "N/A", "error": str(e)}

@router.get("/context-warning")
def api_context_warning(model_id: str = Query(""), max_tokens: int = Query(2048), metadata: str = Query("{}")):
    try:
        meta = json.loads(metadata) if metadata else {}
        warning = update_ctx_warning(model_id, max_tokens, meta)
        return {"warning": warning}
    except Exception as e:
        return {"warning": "", "error": str(e)}

@router.get("/providers")
def api_providers():
    return {"providers": PROVIDER_PRESETS}

@router.get("/benchmarks")
def api_benchmarks():
    benchmarks = [{"label": b[0], "name": b[1]} for b in BENCHMARKS]
    return {"benchmarks": benchmarks}

@router.get("/stats")
def api_get_stats():
    try:
        return get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
