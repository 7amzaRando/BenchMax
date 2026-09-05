# BenchMax REST API

45 REST endpoints under `/api/` — 43 in `backend/api.py` plus `GET /api/health` and `POST /api/shutdown` in `backend/main.py`. Interactive docs (Swagger UI) at **http://localhost:8000/docs** when the server is running.

## Core Endpoints

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/connect` | Connect to API provider | `{api_url, api_key?}` | `{status, models, choices, selected, metadata}` |
| `POST` | `/api/run/start` | Start a benchmark run | `RunRequest` (see below) | `{run_id, message}` |
| `POST` | `/api/batch/start` | Start batch (1 model, N benchmarks) | `BatchRequest` | `{run_id, batch_id, message, summary}` |
| `POST` | `/api/model-queue/start` | Start model queue (N models × M benchmarks) | `ModelQueueRequest` | `{queue_id, message}` |
| `GET` | `/api/model-queue/active` | Get active model queue status | — | `{queue_id, models, current_model_index, ...}` |
| `POST` | `/api/model-queue/halt` | Halt the active model queue | — | `{status}` |
| `POST` | `/api/model-queue/skip` | Skip current model in queue | — | `{status}` |
| `GET` | `/api/run/{id}/status` | Live run status | — | `{run_id, status, accuracy, avg_tps, ...}` |
| `GET` | `/api/poll` | Combined telemetry + progress | `?active_run_id=N` | `{telemetry, run_progress, batch_progress}` |
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
| `GET` | `/api/runs` | List all runs (supports `?offset=N&limit=N`) |
| `GET` | `/api/runs/{id}` | Full run details + per-sample results |
| `GET` | `/api/runs/{id}/diff/{task_id}` | Side-by-side diff for a task |
| `PATCH` | `/api/runs/{id}/notes` | Update run notes/annotations |
| `GET` | `/api/batch/{id}` | Batch summary + charts |
| `GET` | `/api/comparison` | Cross-run comparison (`?run_ids=1,2,3`) |
| `GET` | `/api/export/runs/{id}` | Export run as CSV/JSON/Excel |
| `GET` | `/api/export/batch/{id}` | Export batch as CSV/JSON/Excel |
| `GET` | `/api/export/history` | Export all history as CSV/JSON/Excel |
| `GET` | `/api/export/history/markdown` | Export history as Markdown table |
| `GET` | `/api/export/leaderboard` | Export leaderboard as CSV/JSON/Excel |
| `GET` | `/api/export/comparison` | Export comparison as CSV/JSON/Excel |
| `GET` | `/api/export/runs/{id}/markdown` | Export single run as Markdown report |

## Leaderboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/leaderboard` | Get local leaderboard |
| `DELETE` | `/api/leaderboard/{id}` | Delete leaderboard entry |
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
| `GET` | `/api/telemetry` | System telemetry snapshot |
| `GET` | `/api/benchmarks` | List all benchmarks |
| `POST` | `/api/run/check` | Pre-flight dataset/runtime check |
| `POST` | `/api/shutdown` | Shut down server (localhost only) |

## Error Responses

All endpoints return `{"detail": "Internal server error"}` with HTTP 500 on failure. Detailed error messages are logged server-side but not exposed to clients (prevents API key/path leakage).

## CLI Reference

`cli.py` wraps every endpoint — 38 commands for scripting and agent automation:

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
