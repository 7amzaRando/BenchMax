# BenchMax REST API

52 route handlers under `/api/` — 50 in `backend/api.py` plus `GET /api/health` and `POST /api/shutdown` in `backend/main.py` (48 unique paths: `/hf-token`, `/runs`, `/leaderboard`, and `/leaderboard/settings` each serve two methods). Interactive docs (Swagger UI) at **http://localhost:8000/docs** when the server is running.

**Versioning:** `/api/*` is frozen for back-compat. The same router is also served under `/api/v1/*` (same paths, e.g. `GET /api/v1/poll`) so new clients can pin a versioned base path; future breaking changes go under `/api/v2`.

## Core Endpoints

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/connect` | Connect to API provider | `{api_url, api_key?}` | `{status, models, choices, selected, metadata}` |
| `POST` | `/api/run/start` | Start a benchmark run (HTTP 201; HTTP 429 when 4 runs already active) | `RunRequest` (see below) | `{run_id, message}` |
| `POST` | `/api/batch/start` | Start batch (1 model, N benchmarks) (HTTP 201; HTTP 429 when busy) | `BatchRequest` | `{run_id, batch_id, message, summary}` |
| `POST` | `/api/model-queue/start` | Start model queue (N models × M benchmarks) (HTTP 201) | `ModelQueueRequest` | `{queue_id, message}` |
| `GET` | `/api/model-queue/active` | Get active model queue status | — | `{queue_id, models, current_model_index, ...}` |
| `POST` | `/api/model-queue/halt` | Halt the active model queue | — | `{status}` |
| `POST` | `/api/model-queue/skip` | Skip current model in queue | — | `{status}` |
| `GET` | `/api/run/{id}/status` | Live run status | — | `{run_id, status, accuracy, avg_tps, ...}` |
| `GET` | `/api/poll` | Combined telemetry + progress | `?active_run_id=N` | `{telemetry, run_progress, batch_progress, live_turn}` |
| `GET` | `/api/poll/stream` | Same as `/poll` as SSE stream (3s heartbeat) | `?active_run_id=N` | `text/event-stream` |
| `POST` | `/api/run/{id}/pause` | Pause a run | — | `{status}` |
| `POST` | `/api/run/{id}/resume` | Resume a run | `ResumeRequest` | `{status}` |
| `POST` | `/api/run/{id}/halt` | Halt a run (cannot resume) | — | `{status}` |

## RunRequest / BatchRequest / ModelQueueRequest

All three share a `BaseRunParams` base:

```json
{
  "model": "model-name",
  "benchmark": "HumanEval",
  "api_url": "http://127.0.0.1:1234/v1",
  "api_key": "",
  "temperature": 0.0,
  "max_tokens": 2048,
  "system_prompt": "",
  "quick_test": false,
  "disable_repetition_detection": false,
  "context_length": null
}
```

`BatchRequest` replaces `benchmark` with `benchmarks: ["HumanEval", "MMLU-Pro"]`.
`ModelQueueRequest` adds `models: ["model-a", "model-b"]`.

## Data & Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/runs` | List all runs (`?offset=N&limit=N`, limit capped at 500, `limit=0` = all) |
| `GET` | `/api/runs/{id}` | Full run details + per-sample results (samples paginated via `?sample_offset=N&sample_limit=N`, `sample_limit=0` = all) |
| `DELETE` | `/api/runs?run_ids=1,2` | Delete multiple runs (canonical path; empty/invalid IDs → HTTP 400) |
| `GET` | `/api/runs/{id}/card` | Copy-paste Trusted Card block for a run |
| `GET` | `/api/runs/{id}/diff/{task_id}` | Side-by-side diff for a task |
| `GET` | `/api/runs/{id}/depth-results` | Per-depth results for NIAHS runs |
| `PATCH` | `/api/runs/{id}/notes` | Update run notes/annotations |
| `GET` | `/api/batch/{id}` | Batch summary + charts |
| `GET` | `/api/comparison` | Cross-run comparison (`?run_ids=1,2,3`) |
| `GET` | `/api/export/runs/{id}` | Export run as CSV/JSON/Excel |
| `GET` | `/api/export/batch/{id}` | Export batch as CSV/JSON/Excel |
| `GET` | `/api/export/history` | Export all history as CSV/JSON/Excel |
| `GET` | `/api/export/selected` | Export selected runs (`?run_ids=1,2&format=CSV`) |
| `GET` | `/api/export/history/markdown` | Export history as Markdown table |
| `GET` | `/api/export/leaderboard` | Export leaderboard as CSV/JSON/Excel |
| `GET` | `/api/export/comparison` | Export comparison as CSV/JSON/Excel |
| `GET` | `/api/export/runs/{id}/markdown` | Export single run as Markdown report |

## Leaderboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/leaderboard` | Get local leaderboard |
| `DELETE` | `/api/leaderboard` | Deprecated alias of `DELETE /api/runs` (kept for back-compat) |
| `DELETE` | `/api/leaderboard/{id}` | Deprecated alias of `DELETE /api/runs?run_ids={id}` (kept for back-compat) |
| `POST` | `/api/leaderboard/clear` | Clear all history + leaderboard |
| `POST` | `/api/leaderboard/sync` | Sync to online leaderboard |
| `GET` | `/api/leaderboard/settings` | Get sync settings |
| `POST` | `/api/leaderboard/settings` | Set sync settings |

## Datasets & System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/datasets` | Scan datasets, show install status |
| `POST` | `/api/datasets/install/{name}` | Install a benchmark dataset |
| `POST` | `/api/datasets/install-all` | Install all missing datasets |
| `GET` | `/api/hf-token` | Get HuggingFace token (masked) |
| `POST` | `/api/hf-token` | Set HuggingFace token |
| `POST` | `/api/docker/build` | Build Docker sandbox image (`benchmax-sandbox`) |
| `GET` | `/api/docker/status` | Docker availability + image status |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/telemetry` | System telemetry snapshot |
| `GET` | `/api/benchmarks` | List all benchmarks |
| `POST` | `/api/run/check` | Pre-flight dataset/runtime check |
| `POST` | `/api/shutdown` | Shut down server (localhost only) |
| `GET` | `/api/auth/status` | LAN gate state (open — backing for the login screen) |
| `POST` | `/api/auth/setup` | Set the LAN password (localhost only) |
| `POST` | `/api/auth/login` | Verify LAN password, issue Bearer token |

## Error Responses & Status Codes

- `201` — `POST /api/run/start`, `/api/batch/start`, `/api/model-queue/start` on success.
- `400` — empty/unparseable bulk delete (`DELETE /api/runs`, `/api/leaderboard` with no valid IDs).
- `404` — unknown run (`GET /run/{id}/status`, `PATCH /runs/{id}/notes`, `GET /runs/{id}/card`), empty export (nothing to download).
- `409` — run control refused for the current status (pause a completed run, resume a running run).
- `429` — server busy: 4 benchmark runs already active (`MAX_CONCURRENT_RUNS`); the response names the PENDING row so it can be resumed later.
- `500` — everything else. The body is always the generic `{"detail": "Internal server error"}`; detailed tracebacks are logged server-side only (prevents API key/path leakage).

## CLI Reference

`cli.py` wraps every endpoint — 40 commands for scripting and agent automation:

```powershell
py cli.py serve                                            # Start the server (auto-starts if not running)
py cli.py connect --url http://127.0.0.1:1234              # Connect to LM Studio
py cli.py run --model deepseek-r1 --benchmark HumanEval --wait
py cli.py results --run-id 1 --json                        # Results as JSON
```

| Command | What it does |
|---------|-------------|
| `health` | Check server status |
| `serve --port 8000` | Start the server |
| `set-password` | Set the LAN login password (server machine only) |
| `shutdown` | Stop the server |
| `version` | Show CLI version |
| `connect --url URL` | Connect to LM Studio / API |
| `benchmarks` | List all 30 benchmarks |
| `datasets` | Show dataset install status |
| `install-dataset NAME` | Install a benchmark dataset |
| `install-all` | Install all missing datasets |
| `hf-token --token HF_...` | Get/set HuggingFace token |
| `run --model M --benchmark B` | Run a single benchmark |
| `batch --model M --benchmarks B1 B2` | Run multiple benchmarks |
| `model-queue --models M1 M2 --benchmarks B1 B2` | Run across multiple models |
| `model-queue-active` | Check model queue status |
| `model-queue-halt` | Halt model queue |
| `model-queue-skip` | Skip current model |
| `status --run-id N` | Check run progress (use `--wait` to block until done) |
| `poll --run-id N` | Poll live telemetry |
| `results --run-id N` | Show run results |
| `history` | List all past runs |
| `diff --run-id N --task-id T` | Show answer diff |
| `comparison --run-ids 1,2,3` | Compare runs |
| `pause --run-id N` | Pause a run |
| `resume --run-id N` | Resume a run |
| `halt --run-id N` | Halt a run |
| `export --run-id N --format CSV` | Export results |
| `export-selected --run-ids 1,2 --format CSV` | Export selected runs |
| `export-batch --batch-id UUID` | Export batch results |
| `export-history` | Export all history |
| `batch-status --batch-id UUID` | Check batch status |
| `leaderboard` | View leaderboard |
| `leaderboard-delete --run-id N` | Delete from leaderboard |
| `leaderboard-clear` | Clear leaderboard |
| `leaderboard-sync` | Sync leaderboard online |
| `leaderboard-settings` | Get/set leaderboard settings |
| `telemetry` | Show CPU/RAM/GPU stats |
| `models` | List loaded models |
| `build-docker` | Build Docker sandbox image |
| `docker-status` | Check Docker status |

**Global flags** (before subcommand): `--json` (machine-readable output), `--server URL` (override server address), `--verbose` (debug HTTP traffic on stderr), `--yes` (skip confirmation prompts).

See `AGENT_GUIDE.md` for detailed usage, examples, and agent workflows.
