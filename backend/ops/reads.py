"""History/detail/leaderboard/comparison reads and bulk deletes."""

import json
import logging

import pandas as pd
from sqlalchemy import func as sa_func
from sqlalchemy.orm import joinedload

from backend.database import Run, Result, get_db

from backend.ops.state import (  # noqa: E402
    _halt_events,
    _halt_events_lock,
    _active_threads,
    _active_threads_lock,
)

from backend.ops.stats import (
    _add_scoring_columns, _backfill_category_map, _build_aggregated_token_chart,
    _build_batch_latency_chart, _build_per_category_chart, _build_tps_histogram,
    _build_ttft_histogram, _compute_batch_stats_sql, _compute_result_stats,
    _stored_result_category,
)

logger = logging.getLogger(__name__)


def load_history(offset: int = 0, limit: int = 0) -> tuple[pd.DataFrame, int]:
    """Load run history with aggregated statistics per run.

    Returns a DataFrame with columns: Run ID, Model, Benchmark, Status, Progress,
    Correct, Total, Accuracy, Needles (+Raw), Avg TPS, Avg TTFT, Avg Prompt TPS,
    Avg Tokens, Total Tokens, Thinking Tokens, Response Tokens, Context Length
    (+Raw, K), Temperature, Max Tokens, System Prompt, Quick Test,
    Repetition Detection Off, API URL, Duration, Batch, Notes, Created.
    Supports pagination via offset/limit parameters.

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
                "Thinking Tokens": stats.get("think_tk", 0),
                "Response Tokens": stats.get("resp_tk", 0),
                "Context Length": ctx_str,
                "Context Length Raw": ctx_len_val if ctx_len_val is not None else "",
                "Context K": ctx_k,
                "Temperature": params_dict.get("temperature", ""),
                "Max Tokens": params_dict.get("max_completion_tokens", params_dict.get("max_tokens", "")),
                "System Prompt": params_dict.get("system_prompt") or "",
                "Quick Test": params_dict.get("quick_test", ""),
                "Repetition Detection Off": params_dict.get("disable_repetition_detection", ""),
                "API URL": params_dict.get("api_url", ""),
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
            _quick_test = params_dict.get("quick_test", False)
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
                ctx_line = "Context Length: `65,536 tokens (64K)`  \n"

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
        DataFrame with columns: Run ID, Model, Benchmark, Accuracy, Needles,
        Avg TPS, Avg TTFT, Avg Prompt TPS, Passed, Correct, Total, Tokens,
        Thinking Tokens, Response Tokens, Temperature, Max Tokens,
        System Prompt, API URL, Context Length (+Raw, K), Date, Notes,
        status, QuickTest.
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
                "Correct": ok,
                "Total": n,
                "Tokens": total_tk,
                "Thinking Tokens": stats.get("think_tk", 0),
                "Response Tokens": stats.get("resp_tk", 0),
                "Temperature": params.get("temperature", ""),
                "Max Tokens": params.get("max_completion_tokens", params.get("max_tokens", "")),
                "System Prompt": params.get("system_prompt") or "",
                "API URL": params.get("api_url", ""),
                "Context Length": ctx_str,
                "Context Length Raw": ctx_len_val if ctx_len_val is not None else "",
                "Context K": ctx_k,
                "Date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                "Notes": r.notes or "",
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


def delete_runs(run_ids_csv: str) -> tuple[pd.DataFrame, str]:
    """Delete multiple runs by comma-separated IDs in a single transaction.

    Args:
        run_ids_csv: Comma-separated run IDs (e.g. "1,2,3").

    Returns:
        Tuple of (updated_leaderboard_df, status_message).
    """
    ids = [int(x.strip()) for x in run_ids_csv.split(",") if x.strip().isdigit()]
    if not ids:
        return load_leaderboard(), "No valid run IDs provided."
    with get_db() as db:
        try:
            runs = db.query(Run).filter(Run.id.in_(ids)).all()
            found = sorted(r.id for r in runs)
            for r in runs:
                db.delete(r)
            db.commit()
            missing = [i for i in ids if i not in set(found)]
            msg = f"Deleted {len(found)} run(s): {found}."
            if missing:
                msg += f" Not found: {missing}."
            return load_leaderboard(), msg
        except Exception as e:
            logger.error(f"delete_runs failed: {e}", exc_info=True)
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
                "Model": run.model_name,
                "Benchmark": run.benchmark_name,
                "Status": run.status,
                "Accuracy": stats["accuracy"],
                "Correct": ok,
                "Total": n,
            })
            lat_rows.append({
                "Run": label,
                "Model": run.model_name,
                "Benchmark": run.benchmark_name,
                "Avg TPS": stats["avg_tps"],
                "Avg TTFT (s)": stats["avg_ttft"],
                "Avg Prompt TPS (t/s)": stats["avg_prompt_tps"],
            })
            tok_rows.append({
                "Run": label,
                "Model": run.model_name,
                "Benchmark": run.benchmark_name,
                "Thinking": stats["think_tk"],
                "Response": stats["resp_tk"],
                "Total": total_tk,
                "Avg Tokens/Sample": stats["avg_tokens"],
            })
        return (
            pd.DataFrame(acc_rows) if acc_rows else pd.DataFrame(),
            pd.DataFrame(lat_rows) if lat_rows else pd.DataFrame(),
            pd.DataFrame(tok_rows) if tok_rows else pd.DataFrame(),
        )
