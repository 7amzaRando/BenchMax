"""File exports (CSV/JSON/XLSX/markdown), Trusted Cards, and diffs."""

import html as html_mod
import logging
import os
import re
import time

import pandas as pd

from backend.config import ROOT
from backend.database import Run, Result, get_db
from backend.telemetry.monitor import get_system_metrics


from backend.ops.bench import _instantiate_benchmark, _make_client, _run_async
from backend.ops.stats import (
    _add_scoring_columns,
    _compute_result_stats,
    _compute_run_stats_sql,
)
from backend.ops.reads import load_cross_comparison, load_history, load_leaderboard

logger = logging.getLogger(__name__)

CARD_VERSION = "2.0"


def _run_params_for_export(run) -> dict:
    """Flatten a Run's stored parameters into export-friendly columns."""
    try:
        params = run.get_parameters() if run is not None else {}
    except Exception:
        logger.debug("Export param decode failed, using defaults", exc_info=True)
        params = {}
    if not isinstance(params, dict):
        params = {}
    quick_test = params.get("quick_test")
    if quick_test is None and run is not None:
        quick_test = (run.total_samples or 0) <= 10
    return {
        "model": run.model_name if run is not None else "",
        "benchmark": run.benchmark_name if run is not None else "",
        "run_status": run.status if run is not None else "",
        "temperature": params.get("temperature", ""),
        "max_tokens": params.get("max_completion_tokens", params.get("max_tokens", "")),
        "system_prompt": params.get("system_prompt") or "",
        "quick_test": bool(quick_test),
        "repetition_detection_off": bool(params.get("disable_repetition_detection", False)),
        "context_length": params.get("context_length", ""),
        "api_url": params.get("api_url", ""),
        "batch_id": run.batch_id if run is not None and run.batch_id else "",
    }


def _result_to_export_dict(r, run=None) -> dict:
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
    if run is not None:
        row.update(_run_params_for_export(run))
    return _add_scoring_columns(row, r)


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
    """Exports a single run's results as CSV or JSON. One row per sample with
    full prompt/response text, timing, tokens, errors, benchmark extras, plus
    run-level columns (model, benchmark, status, temperature, max tokens,
    system prompt, quick-test flag, API URL, batch)."""
    with get_db() as db:
        run_id = int(run_id_str)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return None, "Run not found."
        results = db.query(Result).filter(Result.run_id == run_id).order_by(Result.id).all()
        rows = [_result_to_export_dict(r, run) for r in results]
        if not rows:
            return None, "No results to export."
        df = pd.DataFrame(rows)
        return _export_dataframe(df, f"run_{run_id}", format_type)


def export_batch_results(batch_id: str, format_type: str) -> tuple[str | None, str]:
    """Exports all results across a batch as CSV or JSON. Same per-sample detail
    as export_results (full prompt/response text + run-level columns),
    stacked across every run in the batch."""
    with get_db() as db:
        runs = db.query(Run).filter(Run.batch_id == batch_id).order_by(Run.id).all()
        if not runs:
            return None, "Batch not found."
        run_by_id = {r.id: r for r in runs}
        results = db.query(Result).filter(
            Result.run_id.in_([r.id for r in runs])
        ).order_by(Result.run_id, Result.id).all()
        rows = [_result_to_export_dict(r, run_by_id.get(r.run_id)) for r in results]
        if not rows:
            return None, "No results to export."
        df = pd.DataFrame(rows)
        safe_bid = "".join(ch for ch in batch_id[:8] if ch.isalnum() or ch in ("-", "_")) or "batch"
        return _export_dataframe(df, f"batch_{safe_bid}", format_type)


def export_all_history(format_type: str = "CSV") -> tuple[str | None, str]:
    """Exports all completed/failed runs as CSV or JSON via load_history(). Includes per-run summary metrics."""
    df, _ = load_history()
    return _export_dataframe(df, "all_history", format_type)


def export_selected_runs(run_ids_csv: str, format_type: str = "CSV") -> tuple[str | None, str]:
    """Exports per-run summaries for the given comma-separated run IDs (same columns as history export)."""
    wanted = [int(x) for x in (run_ids_csv or "").split(",") if x.strip().isdigit()]
    if not wanted:
        return None, "No run IDs provided."
    df, _ = load_history()
    if df.empty:
        return None, "No history to export."
    sel = df[df["Run ID"].isin(wanted)].copy()
    if sel.empty:
        return None, "No matching runs found."
    sel["__ord"] = sel["Run ID"].apply(lambda v: wanted.index(v) if v in wanted else len(wanted))
    sel = sel.sort_values("__ord").drop(columns="__ord")
    return _export_dataframe(sel, "selected_runs", format_type)


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
    """Generates a detailed Markdown report for a single run: summary stats,
    full configuration (temperature, max tokens, system prompt, flags, API URL,
    context, batch), a compact table of every sample, and the complete
    prompt + model response + error for every failed sample."""
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
        cfg = _run_params_for_export(run)

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
            "| Metric | Value |",
            "|--------|-------|",
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
            "## Configuration",
            "",
            "| Setting | Value |",
            "|---------|-------|",
            f"| Temperature | {cfg['temperature'] if cfg['temperature'] != '' else 'default'} |",
            f"| Max Tokens | {cfg['max_tokens'] if cfg['max_tokens'] != '' else 'default'} |",
            f"| System Prompt | {cfg['system_prompt'] or '—'} |",
            f"| Quick Test | {cfg['quick_test']} |",
            f"| Repetition Detection Off | {cfg['repetition_detection_off']} |",
            f"| Context Length | {cfg['context_length'] if cfg['context_length'] != '' else '—'} |",
            f"| API URL | `{cfg['api_url'] or '—'}` |",
            f"| Batch | `{cfg['batch_id'] or '—'}` |",
            "",
        ]

        lines.append("## All Samples")
        lines.append("")
        lines.append("| Task | Correct | TPS | TTFT (s) | Think | Resp | Error |")
        lines.append("|------|---------|-----|----------|-------|------|-------|")
        for r in results:
            err = (r.error_message or "").replace("|", "\\|").replace("\n", " ")[:120]
            mark = "PASS" if r.correct else "FAIL"
            lines.append(
                f"| {r.task_id or 'unknown'} | {mark} | {r.tps or 0} | "
                f"{r.ttft or 0} | {r.thinking_tokens or 0} | "
                f"{r.response_tokens or 0} | {err} |"
            )
        lines.append("")

        if failed:
            lines.append(f"## Failed Samples — Full Detail ({len(failed)})")
            lines.append("")
            for r in failed:
                task = r.task_id or "unknown"
                lines.append(f"### {task}")
                lines.append("")
                if r.error_message:
                    lines.append(f"**Error:** {r.error_message}")
                    lines.append("")
                lines.append("**Prompt:**")
                lines.append("")
                lines.append("```")
                lines.append(r.prompt or "")
                lines.append("```")
                lines.append("")
                lines.append("**Model Response:**")
                lines.append("")
                lines.append("```")
                lines.append(r.raw_response or "")
                lines.append("```")
                lines.append("")
                if r.extracted_code:
                    lines.append("**Extracted Code:**")
                    lines.append("")
                    lines.append("```")
                    lines.append(r.extracted_code)
                    lines.append("```")
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
            lines.append("## Notes")
            lines.append("")
            lines.append(run.notes)
            lines.append("")

        lines.append("---")
        lines.append("*Generated by BenchMax*")

        md_content = "\n".join(lines)
        os.makedirs(ROOT / "records", exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = ROOT / "records" / f"run_{run_id}_{ts}.md"
        path.write_text(md_content, encoding="utf-8")
        return str(path), f"Exported to {path.name}"


def export_all_history_markdown() -> tuple[str | None, str]:
    """Generates a detailed Markdown report of all runs: a full summary table
    plus a per-run section with stats, configuration, notes, and failed-sample
    errors for every run in history."""
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
        "| Run ID | Model | Benchmark | Status | Correct | Total | Accuracy | Avg TPS | Avg TTFT | Avg Prompt TPS | Total Tokens | Think | Resp | Duration | Date | Notes |",
        "|--------|-------|-----------|--------|---------|-------|----------|---------|----------|----------------|--------------|-------|------|----------|------|-------|",
    ]

    for _, row in df.iterrows():
        rid = row.get("Run ID", "")
        model = row.get("Model", "")
        bench = row.get("Benchmark", "")
        status = row.get("Status", "")
        correct = row.get("Correct", "")
        total = row.get("Total", "")
        acc = row.get("Accuracy", "")
        tps = row.get("Avg TPS", "")
        ttft = row.get("Avg TTFT", "")
        prompt_tps = row.get("Avg Prompt TPS", "")
        tokens = row.get("Total Tokens", "")
        think = row.get("Thinking Tokens", "")
        resp = row.get("Response Tokens", "")
        duration = row.get("Duration", "")
        date = row.get("Created", "")
        notes = str(row.get("Notes", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {rid} | {model} | {bench} | {status} | {correct} | {total} | "
            f"{acc} | {tps} | {ttft} | {prompt_tps} | {tokens} | {think} | "
            f"{resp} | {duration} | {date} | {notes} |"
        )

    lines.append("")
    with get_db() as db:
        for _, row in df.iterrows():
            try:
                rid = int(row.get("Run ID"))
            except (TypeError, ValueError):
                continue
            run = db.query(Run).filter(Run.id == rid).first()
            if not run:
                continue
            cfg = _run_params_for_export(run)
            results = db.query(Result).filter(Result.run_id == rid).order_by(Result.id).all()
            stats = _compute_result_stats(results)
            failed = [r for r in results if not r.correct]
            lines.append(f"## Run #{rid} — {run.model_name} / {run.benchmark_name}")
            lines.append("")
            lines.append(
                f"Status `{run.status}` · Accuracy **{stats['accuracy']}%** "
                f"({stats['correct']}/{stats['total']}) · Avg TPS {stats['avg_tps']} · "
                f"Avg TTFT {stats['avg_ttft']}s · Avg Prompt TPS {stats['avg_prompt_tps']} · "
                f"Tokens {stats['total_tk']:,} (think {stats['think_tk']:,}, "
                f"resp {stats['resp_tk']:,})"
            )
            lines.append("")
            lines.append(
                f"Temperature `{cfg['temperature'] if cfg['temperature'] != '' else 'default'}` · "
                f"Max tokens `{cfg['max_tokens'] if cfg['max_tokens'] != '' else 'default'}` · "
                f"Quick test `{cfg['quick_test']}` · "
                f"Repetition detection off `{cfg['repetition_detection_off']}` · "
                f"Context `{cfg['context_length'] if cfg['context_length'] != '' else '—'}` · "
                f"Batch `{cfg['batch_id'] or '—'}`"
            )
            lines.append("")
            if cfg["system_prompt"]:
                lines.append(f"System prompt: {cfg['system_prompt']}")
                lines.append("")
            if run.notes:
                lines.append(f"Notes: {run.notes}")
                lines.append("")
            if failed:
                lines.append(f"Failed samples ({len(failed)}):")
                lines.append("")
                for r in failed:
                    err = (r.error_message or "wrong answer").replace("\n", " ")[:200]
                    lines.append(f"- **{r.task_id or 'unknown'}**: {err}")
                lines.append("")

    lines.extend(["---", "*Generated by BenchMax*"])

    md_content = "\n".join(lines)
    os.makedirs(ROOT / "records", exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = ROOT / "records" / f"all_history_{ts}.md"
    path.write_text(md_content, encoding="utf-8")
    return str(path), f"Exported to {path.name}"


def _fmt_ctx_k(n) -> str:
    """Format a context length as '262k' (rounded thousands)."""
    try:
        return f"{int(round(int(n) / 1000))}k"
    except Exception:
        return "?"


async def _query_card_model_info(client, model_id: str) -> tuple[dict, dict]:
    """Fetch /api/v0 metadata + /api/v1 native entry for a model id."""
    v0: dict = {}
    v1entry: dict = {}
    try:
        meta = await client.get_models_metadata()
        if isinstance(meta, dict):
            v0 = meta.get(model_id, {}) or {}
    except Exception as e:
        logger.debug(f"card v0 metadata failed: {e}")
    try:
        base = client.base_url.rsplit("/v1", 1)[0] if "/v1" in client.base_url else client.base_url
        resp = await client._get_client().get(f"{base}/api/v1/models", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            entries = data.get("models", data.get("data", []))
            for e in entries:
                if isinstance(e, dict) and (e.get("key") == model_id or e.get("id") == model_id):
                    v1entry = e
                    break
    except Exception as e:
        logger.debug(f"card v1 metadata failed: {e}")
    return v0, v1entry


def build_trusted_card(run_id: int) -> dict:
    """Build a copy-paste Trusted Card block for a single run.

    Model specs are queried live from LM Studio (best effort — falls back
    to '?' when offline); score/timing come from stored results; hardware
    is this machine's current telemetry + OS string.
    """
    from backend.ops.errors import RunNotFoundError

    with get_db() as db:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise RunNotFoundError(run_id)
        stats = _compute_run_stats_sql(db, run_id)
        params = run.get_parameters()
        api_url = params.get("api_url") or "http://127.0.0.1:1234/v1"
        api_key = params.get("api_key") or ""
        model_id = run.model_name
        benchmark = run.benchmark_name or "?"
        date_str = run.created_at.strftime("%Y-%m-%d") if run.created_at else "?"
        acc = stats.get("accuracy", 0.0)
        tps = stats.get("avg_tps", 0.0)
        prompt_tps = stats.get("avg_prompt_tps", 0.0)
        correct = stats.get("correct", 0)
        total = stats.get("total", 0)
        status = run.status or ""
        qt = params.get("quick_test")
        quick_test = bool(qt) if qt is not None else (run.total_samples or 0) <= 10
        # Precise per-sample token/TTFT means (unrounded — _compute_batch_stats_sql rounds ttft to 1dp)
        rows = db.query(Result.thinking_tokens, Result.response_tokens, Result.ttft).filter(Result.run_id == run_id).all()
        n = len(rows) or 1
        think_sum = sum((r[0] or 0) for r in rows)
        resp_sum = sum((r[1] or 0) for r in rows)
        ttfts = [r[2] for r in rows if r[2]]
        avg_tok = round((think_sum + resp_sum) / n, 1)
        avg_ttft = round(sum(ttfts) / len(ttfts), 3) if ttfts else 0.0

    # Live model specs (best effort)
    display_name, publisher, arch = model_id, "?", "?"
    quant, size_gb, max_ctx, loaded_ctx = "?", "?", None, None
    v0, v1e = {}, None
    try:
        client = _make_client(api_url, api_key)

        async def _gather():
            try:
                return await _query_card_model_info(client, model_id)
            finally:
                await client.aclose()

        v0, v1e = _run_async(_gather())
        if v1e:
            display_name = v1e.get("display_name") or model_id
            publisher = v1e.get("publisher") or v0.get("publisher", "?") or "?"
            arch = v1e.get("architecture") or v0.get("arch", "?") or "?"
            q = v1e.get("quantization") or {}
            quant = q.get("name") or v0.get("quantization", "?") or "?"
            sb = v1e.get("size_bytes")
            if sb:
                try:
                    size_gb = f"{float(sb) / (1024 ** 3):.2f}"
                except Exception:
                    size_gb = "?"
            max_ctx = v1e.get("max_context_length") or v0.get("max_context_length")
            for inst in v1e.get("loaded_instances", []) or []:
                cfg = (inst or {}).get("config", {}) or {}
                if cfg.get("context_length"):
                    loaded_ctx = cfg["context_length"]
                    break
        elif v0:
            publisher = v0.get("publisher", "?") or "?"
            arch = v0.get("arch", "?") or "?"
            quant = v0.get("quantization", "?") or "?"
            max_ctx = v0.get("max_context_length")
    except Exception as e:
        logger.debug(f"card model lookup failed: {e}")
    if loaded_ctx is None:
        loaded_ctx = v0.get("loaded_context_length") or max_ctx

    # Hardware (current machine)
    try:
        m = get_system_metrics()
    except Exception:
        logger.debug("Trusted card: telemetry unavailable, using CPU fallback", exc_info=True)
        m = {}
    gpu = (m.get("gpu_name") or "CPU").strip()
    try:
        vram_gb = int(round(float(m.get("vram_total_mb", 0)) / 1024)) if m.get("vram_total_mb") else 0
    except Exception:
        logger.debug("Trusted card: unparsable vram_total_mb %r", m.get("vram_total_mb"), exc_info=True)
        vram_gb = 0
    try:
        ram_gb = int(round(float(m.get("ram_total_gb", 0)))) if m.get("ram_total_gb") else 0
    except Exception:
        logger.debug("Trusted card: unparsable ram_total_gb %r", m.get("ram_total_gb"), exc_info=True)
        ram_gb = 0
    gpu_part = f"{gpu} {vram_gb}GB" if vram_gb else gpu
    hw_str = f"{gpu_part} | {ram_gb}GB RAM"
    acc_str = f"{acc:g}"
    tps_str = f"{tps:g}"
    tok_total = think_sum + resp_sum
    think_pct = round(think_sum * 100 / tok_total) if tok_total else 0
    resp_pct = 100 - think_pct if tok_total else 0
    flags = ""
    if quick_test:
        flags += " [quick-test]"
    if status and status not in ("COMPLETED",):
        flags += f" [{status}]"
    text = (
        f"BenchMax Trusted Card v{CARD_VERSION} | {date_str}\n"
        f"Model: {display_name} ({publisher}/{model_id})\n"
        f"Config: {arch} | {quant} | {size_gb} GB\n"
        f"Context: {_fmt_ctx_k(max_ctx)} max / {_fmt_ctx_k(loaded_ctx)} loaded\n"
        f"Hardware: {hw_str}\n"
        f"Benchmark: Run #{run_id} {benchmark} \u2014 {acc_str}% ({correct}/{total}, {tps_str} tps){flags}\n"
        f"Tokens: {avg_tok} avg (think {think_pct}% \u00b7 resp {resp_pct}%) | TTFT avg {avg_ttft:.3f}s | Prompt {f'{prompt_tps:g} t/s' if prompt_tps else 'n/a'}"
    )
    return {
        "run_id": run_id,
        "text": text,
        "display_name": display_name,
        "publisher": publisher,
        "model_id": model_id,
        "arch": arch,
        "quant": quant,
        "size_gb": size_gb,
        "max_context": max_ctx,
        "loaded_context": loaded_ctx,
        "hardware": hw_str,
        "date": date_str,
        "benchmark": benchmark,
        "accuracy": acc,
        "correct": correct,
        "total": total,
        "status": status,
        "quick_test": quick_test,
        "avg_tps": tps,
        "avg_prompt_tps": prompt_tps,
        "avg_tokens": avg_tok,
        "think_pct": think_pct,
        "resp_pct": resp_pct,
        "avg_ttft": avg_ttft,
    }


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
