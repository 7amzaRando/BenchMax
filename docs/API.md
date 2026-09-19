# BenchMax REST API

62 route handlers under `/api/` — 60 in `backend/api.py` plus `GET /api/health` and `POST /api/shutdown` in `backend/main.py` (57 unique paths; several serve two methods). Interactive docs (Swagger UI) at **http://localhost:8000/docs** when the server is running. MCP lives at `POST /mcp` (Streamable HTTP, outside the `/api` router).

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
| `GET` | `/api/poll` | Combined telemetry + progress | `?active_run_id=N` | `{telemetry, run_progress, batch_progress, live_turn, active_runs}` |
| `GET` | `/api/poll/stream` | Same as `/poll` as SSE stream (3s heartbeat) | `?active_run_id=N` | `text/event-stream` |
| `POST` | `/api/run/{id}/pause` | Pause a run | — | `{status}` |
| `POST` | `/api/run/{id}/resume` | Resume a run | `ResumeRequest` | `{status}` |
| `POST` | `/api/run/{id}/halt` | Halt a run (cannot resume) | — | `{status}` |
| `GET` | `/api/provider` | Saved default provider endpoint | — | `{url, set}` |
| `POST` | `/api/provider` | Validate + probe + save default endpoint | `{url, api_key?}` (key probe-only) | `{url, reachable, latency_ms, models_loaded}` |
| `GET` | `/api/provider/health` | Backend reachable? (`?api_url=` overrides default) | — | `{reachable, latency_ms, models_loaded, models}` |
| `GET` | `/api/models` | Loaded model IDs (`?api_url=` overrides default) | — | `{url, models}` |
| `POST` | `/api/webhooks` | Register run-completion webhook (HTTP 201) | `{url}` | `{id, url}` |
| `GET` | `/api/webhooks` | List webhooks | — | `{webhooks}` |
| `DELETE` | `/api/webhooks/{id}` | Delete a webhook | — | `{status}` |

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

Omit `api_url` to use the saved default provider (`POST /api/provider`); omit `api_key` for local backends. Keys are never stored server-side.

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
| `GET` | `/api/version` | App version + GitHub-release update status (`?refresh=true` bypasses the 24h cache) |
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

`cli.py` wraps every endpoint — 48 commands for scripting and agent automation:

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
| `update-check --refresh` | Check GitHub releases for a newer BenchMax |
| `install-mcp --client all` | Register BenchMax MCP in app configs (claude/opencode/cursor/vscode) |
| `provider` | Show the saved default provider endpoint |
| `provider-set --url URL` | Set the default provider endpoint (validated + probed) |
| `provider-health` | Check the LLM backend is serving (no run burned) |
| `webhook-add --url URL` | Register a run-completion webhook |
| `webhooks` | List run-completion webhooks |
| `webhook-delete --id ID` | Delete a run-completion webhook |

**Global flags** (before subcommand): `--json` (machine-readable output), `--server URL` (override server address), `--verbose` (debug HTTP traffic on stderr), `--yes` (skip confirmation prompts).

## Provider endpoints

BenchMax keeps one server-side default LLM provider (`records/.provider.json`, URL only — API keys stay memory-only). Runs without an explicit `api_url` fall back to it, so an empty or schemeless URL can never reach httpx again:

| Endpoint | What it does |
|----------|-------------|
| `GET /api/provider` | Show the saved default endpoint |
| `POST /api/provider` | Validate + probe + save the default endpoint (`{url, api_key?}` — key is probe-only) |
| `GET /api/provider/health` | Reachability + latency + loaded-model count (`?api_url=` overrides the default) |
| `GET /api/models` | Model IDs loaded at the provider (`?api_url=` overrides the default) |

## Completion webhooks

Register an HTTP(S) URL once; every run that reaches COMPLETED/FAILED/HALTED fires one background JSON POST (`{event: "run.completed", run_id, status, model_name, benchmark_name, samples_done, total_samples}`) so agents don't poll:

| Endpoint | What it does |
|----------|-------------|
| `POST /api/webhooks` | Register a webhook (`{url}` → `{id, url}`) |
| `GET /api/webhooks` | List webhooks |
| `DELETE /api/webhooks/{id}` | Delete a webhook |

## MCP Server

BenchMax speaks the Model Context Protocol two ways (16 tools: benchmarks/history/results/status/control/telemetry plus `set_endpoint`, `get_endpoint`, `list_models`, `check_endpoint_health`, `register_webhook`, `list_webhooks`, `delete_webhook`):

- **Stdio** (same machine): `.venv\Scripts\python mcp_server.py` — point any MCP client at it.
- **Remote** (LAN included): `http://127.0.0.1:8000/mcp` (Streamable HTTP, LAN clients need the Bearer token).

One-command setup writes the entries for you:

```powershell
py cli.py install-mcp                      # stdio entries for all detected apps
py cli.py install-mcp --client claude      # just Claude Desktop
py cli.py install-mcp --remote             # remote /mcp URL entries instead
py cli.py install-mcp --uninstall          # remove them again
```

See `AGENT_GUIDE.md` for detailed usage, examples, and agent workflows.
