"""Business-logic facade (thin re-export layer over backend/ops/*).

Why: operations.py grew into a ~3,300-line god module holding every domain
(run lifecycle, stats, reads, exports, datasets). The implementation now lives
in focused modules under backend/ops/; this file re-exports every public and
private name so existing imports (``from backend.operations import X`` in
api.py, tests, scripts) keep working unchanged. New code should import from
``backend.ops.<domain>`` directly.
"""

import logging
import threading  # noqa: F401  (re-exported so ops.threading patch paths keep working)


# Shared mutable state — single source of truth lives in backend/ops/state.py.
# This module re-exports the names so existing imports
# (``from backend.operations import telemetry_history`` etc.) keep working.
# IMPORTANT: scalar/list rebinds must go through ``_state`` attribute writes
# or the helpers in state.py — never bare ``X = ...`` (that would fork the
# binding and split the state again).
import backend.ops.state as _state  # noqa: E402,F401
from backend.ops.state import (  # noqa: E402,F401
    MAX_HISTORY_LEN,
    telemetry_history,
    _docker_daemon_running,
    _halt_events,
    _EMA_ALPHA,
    _LB_SUPABASE_KEY,
    _LB_API_URL,
    _batch_lock,
    _halt_events_lock,
    _telemetry_lock,
    _active_threads,
    _active_threads_lock,
    _model_queue_state,
    _model_queue_lock,
    MAX_CONCURRENT_RUNS,
    _run_slots,
)
from backend.ops.bench import (  # noqa: E402,F401
    BENCHMARK_CLASSES,
    _build_run_params,
    _make_client,
    _run_async,
    _instantiate_benchmark,
)
from backend.ops.stats import (  # noqa: E402,F401
    _update_telemetry_history,
    _add_scoring_columns,
    _stored_result_category,
    _sample_category_for_benchmark,
    _backfill_category_map,
    _compute_run_stats_sql,
    _compute_batch_stats_sql,
    _compute_run_progress,
    _build_token_stats_str,
    _compute_result_stats,
    _build_histogram,
    _build_tps_histogram,
    _build_ttft_histogram,
    _build_aggregated_token_chart,
    _build_per_category_chart,
    _build_batch_latency_chart,
    _build_batch_summary,
    get_run_status,
    get_run_meta,
    get_depth_results,
    build_poll_payload,
    poll,
)
from backend.ops.lifecycle import (  # noqa: E402,F401
    _start_benchmark_thread,
    _chain_batch,
    trigger_run,
    start_batch,
    pause_run,
    resume_run,
    halt_run,
    update_run_notes,
)
from backend.ops.modelqueue import (  # noqa: E402,F401
    _queue_skip_model_requested,
    _clear_skip_model_flag,
    _queue_halted,
    _run_model_queue_in_thread,
    start_model_queue,
    get_model_queue_state,
    halt_model_queue,
    skip_current_model,
)
from backend.ops.reads import (  # noqa: E402,F401
    load_history,
    load_run_details,
    load_batch_summary,
    load_leaderboard,
    delete_leaderboard_entry,
    delete_runs,
    clear_all_history,
    load_cross_comparison,
)
from backend.ops.exports import (  # noqa: E402,F401
    CARD_VERSION,
    _run_params_for_export,
    _result_to_export_dict,
    _export_dataframe,
    export_results,
    export_batch_results,
    export_all_history,
    export_selected_runs,
    export_leaderboard,
    export_comparison,
    export_run_markdown,
    export_all_history_markdown,
    _fmt_ctx_k,
    _query_card_model_info,
    build_trusted_card,
    generate_diff,
)
from backend.ops.datasets import (  # noqa: E402,F401
    _dataset_scan_cache,
    _dataset_scan_cache_time,
    _DATASET_SCAN_CACHE_TTL,
    HF_TOKEN_FILE,
    LB_SETTINGS_FILE,
    _dataset_files,
    _docker_runtime_issues,
    check_benchmark_readiness,
    _scan_datasets,
    connect_lm_studio,
    install_dataset,
    install_all_missing,
    build_docker_image,
    get_docker_status,
    _load_hf_token,
    _harden_secret_file,
    _save_hf_token,
    save_lb_api_key,
    load_lb_settings,
    sync_to_online_leaderboard,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BENCHMARK_CLASSES",
    "_build_run_params", "_make_client", "_run_async", "_instantiate_benchmark",
    "telemetry_history", "MAX_HISTORY_LEN", "_EMA_ALPHA",
    "poll", "trigger_run", "start_batch", "pause_run", "resume_run", "halt_run",
    "start_model_queue", "get_model_queue_state", "halt_model_queue", "skip_current_model",
    "connect_lm_studio", "check_benchmark_readiness",
    "load_history", "load_run_details", "load_batch_summary", "load_leaderboard",
    "load_cross_comparison", "generate_diff", "build_trusted_card",
    "export_results", "export_batch_results", "export_all_history", "export_selected_runs",
    "export_leaderboard", "export_comparison", "export_run_markdown", "export_all_history_markdown",
    "delete_runs", "delete_leaderboard_entry", "clear_all_history",
    "install_dataset", "install_all_missing", "build_docker_image", "get_docker_status",
    "save_lb_api_key", "load_lb_settings", "sync_to_online_leaderboard",
    "get_run_status", "get_run_meta", "update_run_notes", "get_depth_results", "build_poll_payload",
]
