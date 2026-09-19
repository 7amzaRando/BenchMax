import asyncio
import functools
import inspect
import logging
import math
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Body, Request
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

_EXPORT_MIME = {
    "CSV": "text/csv",
    "JSON": "application/json",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
from backend.telemetry.monitor import get_system_metrics  # noqa: E402
from backend.operations import (  # noqa: E402
    connect_lm_studio, trigger_run, start_batch, pause_run, resume_run, halt_run,
    load_history, load_run_details, load_batch_summary,
    load_leaderboard, delete_leaderboard_entry, delete_runs,
    clear_all_history, load_cross_comparison, export_results, export_batch_results,
    export_all_history, generate_diff,
    export_leaderboard, export_comparison, export_run_markdown,
    export_all_history_markdown,
    _scan_datasets, install_dataset, install_all_missing,
    _load_hf_token, _save_hf_token,
    save_lb_api_key, load_lb_settings, sync_to_online_leaderboard,
    poll,
    start_model_queue, get_model_queue_state, halt_model_queue, skip_current_model,
    check_benchmark_readiness,
    build_docker_image, get_docker_status,
    build_trusted_card, export_selected_runs,
    get_run_status, get_run_meta, update_run_notes, get_depth_results,
    build_poll_payload,
    get_version_info,
    get_mcp_info,
    install_mcp_configs,
    get_default_provider, set_default_provider,
    resolve_api_url, check_provider_health, list_provider_models,
    register_webhook, list_webhooks, delete_webhook,
)
from backend.config import BENCHMARKS  # noqa: E402
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


def _map_service_error(exc: Exception):
    """Map typed service-layer errors (backend/ops/errors.py) to HTTP codes.

    RunNotFoundError/NothingToExportError → 404, RunStateError → 409,
    NoValidIdsError → 400. Returns None when the exception is unmapped.
    """
    from backend.ops.errors import (
        NoValidIdsError,
        NothingToExportError,
        RunNotFoundError,
        RunStateError,
    )

    if isinstance(exc, (RunNotFoundError, NothingToExportError)):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RunStateError):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, NoValidIdsError):
        raise HTTPException(status_code=400, detail=str(exc))
    return None


def handle_api_errors(_func=None, *, operation=None):
    """Decorator replacing per-endpoint try/except _handle_api_error blocks.

    Wraps sync and async handlers: HTTPException passes through untouched,
    typed service errors map to 404/409/400 via _map_service_error(), and
    any other exception is logged (with traceback) and converted to a
    generic 500 via _handle_api_error(). The operation label defaults to
    "<func_name> failed" so call sites no longer hand-maintain strings.
    """
    def decorator(func):
        op = operation or f"{func.__name__} failed"
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except HTTPException:
                    raise
                except Exception as e:
                    _map_service_error(e)
                    _handle_api_error(op)
            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                _map_service_error(e)
                _handle_api_error(op)
        return sync_wrapper

    if _func is not None and callable(_func):
        return decorator(_func)
    return decorator


def _run_control_error(status: str, run_id: int):
    """Map legacy string-returning control-plane results to HTTP codes.

    ``pause_run``/``halt_run``/``resume_run`` return status strings for
    back-compat (tests + CLI pin them). "Run not found." → 404,
    "Cannot …" refusals → 409 Conflict, anything else starting with a
    failure → 500. Success strings pass through untouched.
    """
    if status == "Run not found.":
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if status.startswith("Cannot ") or "could not resume" in status:
        raise HTTPException(status_code=409, detail=status)
    return status


def _export_file_or_404(file_path, status: str, export_format: str, markdown: bool = False):
    """Shared export responder: file download on success, 404 otherwise.

    Previously each of the 8 export endpoints inlined its own
    ``if file_path: FileResponse … else: 200-JSON`` branch, so an empty
    export downloaded a bogus ``{"status": …, "file": null}`` JSON file.
    """
    if file_path:
        media = "text/markdown" if markdown else _EXPORT_MIME.get(export_format, "application/octet-stream")
        return FileResponse(file_path, filename=Path(file_path).name, media_type=media)
    raise HTTPException(status_code=404, detail=status or "Nothing to export")


@router.post("/connect")
@handle_api_errors
async def api_connect(req: ConnectRequest):
    """Connect to an LM Studio instance and list available models."""
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

class ProviderBody(BaseModel):
    url: str = ""
    api_key: str = ""  # probe-only: verifies the endpoint, never stored


@router.get("/provider")
@handle_api_errors
def api_get_provider():
    """Server-side default LLM provider (URL only — keys are memory-only)."""
    return get_default_provider()


@router.post("/provider")
@handle_api_errors
async def api_set_provider(body: ProviderBody):
    """Set the default provider endpoint. The URL is validated (needs an
    http(s) scheme), probed for reachability, and persisted; runs without
    an explicit api_url fall back to it. The api_key is probe-only."""
    try:
        return await set_default_provider(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/provider/health")
@handle_api_errors
async def api_provider_health(api_url: str = ""):
    """Is the LLM backend serving? Times GET <url>/models (explicit URL or
    saved default) and counts loaded models. Never 500s."""
    return await check_provider_health(api_url)


@router.get("/models")
@handle_api_errors
async def api_list_models(api_url: str = ""):
    """Model IDs currently loaded at the provider (explicit URL or default)."""
    return await list_provider_models(api_url)


@router.get("/datasets")
@handle_api_errors
def api_scan_datasets():
    """Scan the data/ directory and report which datasets are installed."""
    df = _scan_datasets()
    return {"datasets": _df_to_dict(df)}

@router.post("/datasets/install/{bench_name}")
@handle_api_errors
async def api_install_dataset(bench_name: str, req: InstallRequest = Body(default=InstallRequest())):
    """Download and install the full dataset for a given benchmark."""
    status = await install_dataset(bench_name, req.hf_token)
    return {"status": status}

@router.post("/datasets/install-all")
@handle_api_errors
async def api_install_all(req: InstallRequest = Body(default=InstallRequest())):
    """Install all missing datasets at once."""
    result = await install_all_missing(req.hf_token)
    return {"status": result}

@router.get("/hf-token")
@handle_api_errors
def api_get_hf_token():
    """Return the stored HuggingFace API token (masked for UI display)."""
    token = _load_hf_token()
    masked = token[:4] + "****" + token[-4:] if len(token) > 8 else "****" if token else ""
    return {"token": masked}


@router.post("/hf-token")
@handle_api_errors
def api_set_hf_token(req: HfTokenRequest):
    """Save a HuggingFace API token for dataset downloads."""
    return {"status": _save_hf_token(req.token)}


@router.post("/run/start", status_code=201)
@handle_api_errors
def api_trigger_run(req: RunRequest):
    """Start a single benchmark run with the given model and parameters.

    Args:
        req: RunRequest with model, benchmark, and optional temperature/max_tokens/system_prompt.

    Returns:
        dict: {"run_id": int, "message": str} on success.

    Raises:
        HTTPException: 500 if the run cannot be started.
    """
    run_id, msg = trigger_run(
        req.model, req.benchmark, resolve_api_url(req.api_url), req.api_key,
        req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
        req.disable_repetition_detection, req.context_length,
    )
    if msg.startswith("Server busy"):
        raise HTTPException(
            status_code=429,
            detail={"message": msg, "run_id": run_id},
        )
    return {"run_id": run_id, "message": msg}


@router.post("/batch/start", status_code=201)
@handle_api_errors
def api_start_batch(req: BatchRequest):
    """Start a batch of benchmarks (multiple benchmarks, single model)."""
    first_run_id, batch_id, msg, summary_df, batch_id_display = start_batch(
        req.model, req.benchmarks, resolve_api_url(req.api_url), req.api_key,
        req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
        req.disable_repetition_detection, req.context_length,
    )
    if msg.startswith("Server busy"):
        raise HTTPException(
            status_code=429,
            detail={
                "message": msg,
                "run_id": first_run_id,
                "batch_id": batch_id,
            },
        )
    return {
        "run_id": first_run_id,
        "batch_id": batch_id,
        "message": msg,
        "summary": _df_to_dict(summary_df),
        "batch_id_display": batch_id_display,
    }


@router.post("/model-queue/start", status_code=201)
@handle_api_errors
def api_start_model_queue(req: ModelQueueRequest):
    """Start a model queue run (multiple models, multiple benchmarks, sequential)."""
    model_benchmarks = [(m, req.benchmarks) for m in req.models]
    queue_id, msg = start_model_queue(
        model_benchmarks, resolve_api_url(req.api_url), req.api_key,
        req.temperature, req.max_tokens, req.system_prompt, req.quick_test,
        req.disable_repetition_detection, req.context_length,
    )
    return {"queue_id": queue_id, "message": msg}


class RunCheckRequest(BaseRunParams):
    benchmarks: list[str]

@router.post("/run/check")
@handle_api_errors
def api_check_run_readiness(req: RunCheckRequest):
    """Check whether the selected benchmark(s) are ready to run (datasets/runtime installed)."""
    issues = []
    for bn in req.benchmarks:
        issues.extend(check_benchmark_readiness(bn, req.quick_test))
    blocking = [i for i in issues if i.get("severity", "blocking") == "blocking"]
    warnings = [i for i in issues if i.get("severity") == "warning"]
    return {"ok": len(blocking) == 0, "issues": blocking, "warnings": warnings}


@router.get("/model-queue/active")
@handle_api_errors
def api_active_model_queue():
    """Get the current state of the model queue (if active)."""
    state = get_model_queue_state()
    return state


@router.post("/model-queue/halt")
@handle_api_errors
def api_halt_model_queue():
    """Halt the currently running model queue and unload the active model."""
    status = halt_model_queue()
    return {"status": status}


@router.post("/model-queue/skip")
@handle_api_errors
def api_skip_model_queue():
    """Skip the currently running model and advance to the next in the queue."""
    status = skip_current_model()
    return {"status": status}


@router.post("/run/{run_id}/pause")
@handle_api_errors
def api_pause_run(run_id: int):
    """Pause an active benchmark run. Can be resumed later."""
    status = pause_run(run_id)
    return {"status": _run_control_error(status, run_id)}


@router.post("/run/{run_id}/resume")
@handle_api_errors
def api_resume_run(run_id: int, req: ResumeRequest):
    """Resume a paused/halted/failed (or shutdown-interrupted) benchmark run from its saved position. Uses the run's stored settings when present."""
    status = resume_run(run_id, resolve_api_url(req.api_url), req.api_key, req.temperature, req.max_tokens, req.system_prompt, req.quick_test, req.disable_repetition_detection, req.context_length)
    return {"status": _run_control_error(status, run_id)}


@router.post("/run/{run_id}/halt")
@handle_api_errors
def api_halt_run(run_id: int):
    """Halt (terminate) a benchmark run. Cannot be resumed."""
    status = halt_run(run_id)
    return {"status": _run_control_error(status, run_id)}


@router.get("/run/{run_id}/status")
@handle_api_errors
def api_run_status(run_id: int):
    """Get live status and aggregated metrics for a benchmark run.

    Args:
        run_id: The run's primary key.

    Returns:
        dict: run_id, model_name, benchmark_name, status, current_index,
              total_samples, avg_tps, avg_ttft, accuracy, token stats, etc.
    """
    return get_run_status(run_id)


@router.get("/runs")
@handle_api_errors
def api_load_history(offset: int = Query(0, ge=0), limit: int = Query(0, ge=0, le=500)):
    """Load the run history (paginated; ``limit=0`` returns all, capped at 500 per page)."""
    df, total = load_history(offset=offset, limit=limit)
    return {"runs": _df_to_dict(df), "total": total, "offset": offset, "limit": limit}


@router.get("/runs/{run_id}")
@handle_api_errors
def api_load_run_details(
    run_id: int,
    sample_offset: int = Query(0, ge=0),
    sample_limit: int = Query(0, ge=0, le=2000),
):
    """Load detailed results, token charts, and histograms for a single run.

    ``sample_offset``/``sample_limit`` paginate the per-sample table only
    (``sample_limit=0`` returns all samples — the previous default, kept for
    back-compat with the History tab and CLI).
    """
    summary, samples_df, failed_choices, token_df, ttft_hist, tps_hist, cat_chart = load_run_details(str(run_id))
    meta = get_run_meta(run_id)
    samples = _df_to_dict(samples_df)
    total_samples = len(samples)
    if sample_limit > 0:
        samples = samples[sample_offset:sample_offset + sample_limit]
    return {
        "summary": summary,
        "benchmark_name": meta["benchmark_name"],
        "context_length": meta["context_length"],
        "samples": samples,
        "samples_total": total_samples,
        "sample_offset": sample_offset,
        "sample_limit": sample_limit,
        "failed_tasks": failed_choices if isinstance(failed_choices, list) else [],
        "selected_failed": failed_choices[0] if (isinstance(failed_choices, list) and failed_choices) else None,
        "token_chart": _df_to_dict(token_df),
        "ttft_histogram": _df_to_dict(ttft_hist),
        "tps_histogram": _df_to_dict(tps_hist),
        "category_chart": _df_to_dict(cat_chart),
    }


@router.get("/runs/{run_id}/card")
@handle_api_errors
def api_trusted_card(run_id: int):
    """Build a copy-paste Trusted Card block for a single run."""
    return sanitize_for_json(build_trusted_card(run_id))



@router.get("/runs/{run_id}/diff/{task_id:path}")
@handle_api_errors
def api_generate_diff(run_id: int, task_id: str):
    """Generate a unified diff between the expected answer and model output for a specific task."""
    html = generate_diff(str(run_id), task_id)
    return {"html": html}


class NotesBody(BaseModel):
    notes: str = ""


@router.patch("/runs/{run_id}/notes")
@handle_api_errors
def api_update_notes(run_id: int, body: NotesBody = Body(...)):
    """Update the notes field for a run."""
    notes = update_run_notes(run_id, body.notes)
    return {"status": "ok", "notes": notes}


@router.get("/runs/{run_id}/depth-results")
@handle_api_errors
def api_depth_results(run_id: int):
    """Get per-sample correctness and depth for NIAHS depth analysis chart.

    Supports both legacy single-needle schema (one depth per Result) and the
    new multi-needle schema (5 depths per Result via per_depth_correct).
    """
    return {"results": get_depth_results(run_id)}


@router.get("/batch/{batch_id}")
@handle_api_errors
def api_batch_summary(batch_id: str):
    """Get the summary, accuracy chart, and latency chart for a batch."""
    summary_df, chart_df, latency_df = load_batch_summary(batch_id)
    return {
        "summary": _df_to_dict(summary_df),
        "chart": _df_to_dict(chart_df),
        "latency_chart": _df_to_dict(latency_df),
    }


@router.get("/export/runs/{run_id}")
@handle_api_errors
def api_export_results(run_id: int, export_format: str = Query("CSV", alias="format")):
    """Export a single run's results as CSV, JSON, or Excel file download."""
    file_path, status = export_results(str(run_id), export_format)
    return _export_file_or_404(file_path, status, export_format)


@router.get("/export/batch/{batch_id}")
@handle_api_errors
def api_export_batch(batch_id: str, export_format: str = Query("CSV", alias="format")):
    """Export results for an entire batch as CSV, JSON, or Excel file download."""
    file_path, status = export_batch_results(batch_id, export_format)
    return _export_file_or_404(file_path, status, export_format)


@router.get("/export/history")
@handle_api_errors
def api_export_history(export_format: str = Query("CSV", alias="format")):
    """Export all run history as a CSV, JSON, or Excel file download."""
    file_path, status = export_all_history(export_format)
    return _export_file_or_404(file_path, status, export_format)


@router.get("/export/selected")
@handle_api_errors
def api_export_selected(run_ids: str = Query(""), export_format: str = Query("CSV", alias="format")):
    """Export per-run summaries for selected run IDs as CSV, JSON, or Excel file download."""
    file_path, status = export_selected_runs(run_ids, export_format)
    return _export_file_or_404(file_path, status, export_format)


@router.get("/export/history/markdown")
@handle_api_errors
def api_export_history_markdown():
    """Export all run history as a Markdown summary table."""
    file_path, status = export_all_history_markdown()
    return _export_file_or_404(file_path, status, "", markdown=True)


@router.get("/export/leaderboard")
@handle_api_errors
def api_export_leaderboard(export_format: str = Query("CSV", alias="format")):
    """Export the leaderboard as CSV, JSON, or Excel file download."""
    file_path, status = export_leaderboard(export_format)
    return _export_file_or_404(file_path, status, export_format)


@router.get("/export/comparison")
@handle_api_errors
def api_export_comparison(run_ids: str = Query(""), export_format: str = Query("CSV", alias="format")):
    """Export cross-run comparison as CSV, JSON, or Excel file download."""
    file_path, status = export_comparison(run_ids, export_format)
    return _export_file_or_404(file_path, status, export_format)


@router.get("/export/runs/{run_id}/markdown")
@handle_api_errors
def api_export_run_markdown(run_id: int):
    """Export a single run as a Markdown report."""
    file_path, status = export_run_markdown(str(run_id))
    return _export_file_or_404(file_path, status, "", markdown=True)


@router.get("/comparison")
@handle_api_errors
def api_comparison(run_ids: str = Query("")):
    """Compare accuracy, latency, and tokens across multiple runs by comma-separated IDs."""
    acc_df, latency_df, token_df = load_cross_comparison(run_ids)
    return {
        "accuracy": _df_to_dict(acc_df),
        "latency": _df_to_dict(latency_df),
        "tokens": _df_to_dict(token_df),
    }


@router.get("/leaderboard")
@handle_api_errors
def api_leaderboard():
    """Get the local leaderboard with all completed runs."""
    df = load_leaderboard()
    return {"leaderboard": _df_to_dict(df)}


@router.delete("/runs")
@handle_api_errors
def api_delete_runs_canonical(run_ids: str = Query("")):
    """Delete multiple runs by comma-separated IDs (canonical resource path)."""
    if not run_ids.strip():
        raise HTTPException(status_code=400, detail="No valid run IDs provided.")
    lb_df, status = delete_runs(run_ids)
    if status == "No valid run IDs provided.":
        raise HTTPException(status_code=400, detail=status)
    return {"leaderboard": _df_to_dict(lb_df), "status": status}

@router.delete("/leaderboard")
@handle_api_errors
def api_delete_runs(run_ids: str = Query("")):
    """Delete multiple runs by comma-separated IDs.

    Deprecated alias of ``DELETE /api/runs`` — kept so the History tab,
    CLI, and existing scripts keep working.
    """
    if not run_ids.strip():
        raise HTTPException(status_code=400, detail="No valid run IDs provided.")
    lb_df, status = delete_runs(run_ids)
    if status == "No valid run IDs provided.":
        raise HTTPException(status_code=400, detail=status)
    return {"leaderboard": _df_to_dict(lb_df), "status": status}

@router.delete("/leaderboard/{run_id}")
@handle_api_errors
def api_delete_leaderboard(run_id: int):
    """Delete a single entry from the leaderboard by run ID.

    Deprecated alias of ``DELETE /api/runs?run_ids={id}`` — kept for back-compat.
    """
    lb_df, status = delete_leaderboard_entry(str(run_id))
    return {"leaderboard": _df_to_dict(lb_df), "status": status}


@router.post("/leaderboard/clear")
@handle_api_errors
def api_clear_leaderboard(req: ConfirmClear):
    """Clear the entire run history and leaderboard (requires confirmation text)."""
    history_df, lb_df, status = clear_all_history(req.confirm_text)
    return {
        "history": _df_to_dict(history_df),
        "leaderboard": _df_to_dict(lb_df),
        "status": status,
    }


@router.get("/leaderboard/settings")
@handle_api_errors
def api_lb_settings():
    """Get the stored online leaderboard sync API key (masked for UI display)."""
    key = load_lb_settings()
    masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****" if key else ""
    return {"api_key": masked}


@router.post("/leaderboard/settings")
@handle_api_errors
def api_save_lb_settings(req: ApiKeyRequest):
    """Save the online leaderboard sync API key."""
    return {"status": save_lb_api_key(req.api_key)}


@router.post("/leaderboard/sync")
@handle_api_errors
async def api_sync_leaderboard(req: ApiKeyRequest = Body(default=ApiKeyRequest(api_key=""))):
    """Sync the local leaderboard to the configured online endpoint."""
    status = await sync_to_online_leaderboard(1, api_key=req.api_key)
    return {"status": status}


@router.get("/telemetry")
@handle_api_errors
def api_telemetry():
    """Get the latest system telemetry snapshot (CPU, RAM, GPU, VRAM). Used by HardwareTab for live monitoring."""
    metrics = get_system_metrics()
    return metrics



@router.get("/poll")
@handle_api_errors
def api_poll(active_run_id: int = Query(default=0)):
    """Combined polling endpoint: returns telemetry, run progress, and batch progress in one call.

    Args:
        active_run_id: ID of the currently active run (0 or omitted for no active run).

    Returns:
        dict: telemetry (cpu/ram/gpu), run_progress (accuracy, tps, ttft, tokens),
              batch_progress (summary, ETA, per-benchmark chart data).
    """
    return build_poll_payload(poll(active_run_id or None))


@router.get("/poll/stream")
async def api_poll_stream(active_run_id: int = Query(default=0)):
    """SSE stream alternative to GET /poll — pushes same JSON every 3s via text/event-stream."""
    import orjson

    async def gen():
        yield "retry: 3000\n\n"
        while True:
            try:
                result = await asyncio.to_thread(poll, active_run_id or None)
                payload = build_poll_payload(result)
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
@handle_api_errors
def api_benchmarks():
    """Return the list of all available benchmarks with display labels and internal names."""
    from backend.config import BENCHMARK_META
    benchmarks = []
    for label, name in BENCHMARKS:
        meta = BENCHMARK_META.get(name, {})
        benchmarks.append({
            "label": label,
            "name": name,
            "category": meta.get("category", "Other"),
            "docker": bool(meta.get("docker")),
            "docker_partial": bool(meta.get("docker_partial", False)),
            "samples": meta.get("samples", 0),
            "short": meta.get("short", ""),
        })
    return {"benchmarks": benchmarks}


@router.post("/docker/build")
@handle_api_errors
async def api_build_docker():
    """Build the benchmax-sandbox Docker image with all runtimes."""
    status = await build_docker_image()
    return {"status": status}



@router.get("/docker/status")
@handle_api_errors
async def api_docker_status():
    """Check Docker availability and image status."""
    return await get_docker_status()


@router.get("/version")
def api_version(refresh: bool = Query(default=False)):
    """App version + GitHub-release update status. Never 500s: offline or
    rate-limited checks return latest=None so the UI fails silent."""
    return get_version_info(refresh=refresh)


@router.get("/mcp/info")
def api_mcp_info():
    """MCP access info (endpoint, tools, stdio command) for the Settings
    tab. Never 500s: a missing mcp package yields mounted=False."""
    return get_mcp_info()


class McpInstallBody(BaseModel):
    clients: list[str] = ["all"]
    url: str = ""
    remote: bool = False
    uninstall: bool = False


@router.post("/mcp/install")
async def api_mcp_install(request: Request, body: McpInstallBody):
    """Write/remove the benchmax entry in MCP client configs on the server
    machine. Localhost only — a LAN visitor must not rewrite the owner's
    app configs (same rule as POST /api/auth/setup)."""
    from backend import auth as lan_auth
    if not lan_auth.is_loopback_request(request):
        raise HTTPException(status_code=403, detail="Install MCP from the server machine itself.")
    try:
        wrote = install_mcp_configs(body.url, clients=body.clients,
                                    remote=body.remote, uninstall=body.uninstall)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    action = "removed from" if body.uninstall else "written to"
    return {"status": "ok", "action": action, "configs": wrote}


class WebhookBody(BaseModel):
    url: str = ""


@router.post("/webhooks", status_code=201)
@handle_api_errors
def api_register_webhook(body: WebhookBody):
    """Register a run-completion webhook (fired on COMPLETED/FAILED/HALTED)."""
    try:
        return register_webhook(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/webhooks")
@handle_api_errors
def api_list_webhooks():
    """List registered completion webhooks."""
    return {"webhooks": list_webhooks()}


@router.delete("/webhooks/{hook_id}")
@handle_api_errors
def api_delete_webhook(hook_id: str):
    """Remove a completion webhook."""
    if not delete_webhook(hook_id):
        raise HTTPException(status_code=404, detail=f"Unknown webhook {hook_id}.")
    return {"status": "deleted"}



class LanPasswordBody(BaseModel):
    password: str = ""


@router.get("/auth/status")
def api_auth_status(request: Request):
    """LAN gate state for the login screen. Never requires auth itself."""
    from backend import auth as lan_auth
    loopback = lan_auth.is_loopback_request(request)
    authed = lan_auth.lan_request_allowed(request)
    return {
        "lan_required": not loopback,
        "password_set": lan_auth.password_is_set(),
        "authenticated": authed,
    }


@router.post("/auth/setup")
async def api_auth_setup(request: Request, body: LanPasswordBody):
    """Set (or replace) the LAN password. Localhost only — LAN callers
    can never set the password, so a stranger can't claim an unset server."""
    from backend import auth as lan_auth
    if not lan_auth.is_loopback_request(request):
        raise HTTPException(status_code=403, detail="Set the password from the server machine first.")
    try:
        lan_auth.set_password(body.password)
        return {"status": "saved"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/login")
async def api_auth_login(body: LanPasswordBody):
    """Verify the LAN password and issue a Bearer token."""
    from backend import auth as lan_auth
    if not lan_auth.password_is_set():
        raise HTTPException(status_code=409, detail="No LAN password set yet — ask the server owner to set one.")
    if not lan_auth.verify_password(body.password or ""):
        raise HTTPException(status_code=401, detail="Wrong password.")
    token, _ = lan_auth.issue_token()
    return {"token": token}
