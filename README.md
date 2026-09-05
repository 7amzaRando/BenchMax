# BenchMax

**Local LLM Benchmarking Suite** — Evaluate any LLM against 29 standardized benchmarks. Works with LM Studio, Ollama, OpenAI, and any OpenAI-compatible endpoint.

[![Python 3.11+](https://img.shields.io/badge/Python_3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React_19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![CI](https://github.com/7amzaRando/BenchMax/actions/workflows/ci.yml/badge.svg)](https://github.com/7amzaRando/BenchMax/actions/workflows/ci.yml)

---

## Overview

BenchMax is a **free and open-source** LLM benchmarking platform. Point it at any OpenAI-compatible API endpoint (local or cloud), select a benchmark, and get standardized scores across code generation, math reasoning, instruction following, function calling, safety, vision, and long-context tasks.

All benchmarks run **entirely locally** — no cloud services required. The 5 code benchmarks (HumanEval, BigCodeBench ×2, LiveCodeBench, Aider Polyglot) run in Docker (`benchmax-sandbox`); the other 24 need no Docker at all.

Created by [**Rando**](https://github.com/7amzaRando).

---

## Features

| Feature | Description |
|---------|-------------|
| **30 Benchmarks** | HumanEval, MMLU-Pro, IFEval, AIME, BigCodeBench, BigCodeBench-Hard, BFCL, UncensorBench, Aider Polyglot, LongBench-v2, MMMU-Pro, LiveBench, LiveCodeBench, BenchMax Personal, BenchMax Lite, BenchMax Code, BenchMax Reason, BenchMax Tectonic, Writing Speed Test, Coding Speed Test, TruthfulQA, HellaSWAG, WinoGrande, ARC-Challenge, CommonSenseQA, Long Context Memory, NIAHS, GAIA, Tau3-Airline, BenchMax ToolCall |
| **8 API Providers** | LM Studio, Ollama, OpenAI, OpenRouter, Groq, DeepSeek, AIMLAPI, SiliconFlow — any OpenAI-compatible endpoint |
| **Live Inference Metrics** | TTFT, TPS, per-sample timing, token counts — streamed in real time via 3s polling |
| **Hardware Telemetry** | CPU, RAM, GPU load, VRAM, temperature — NVIDIA & AMD (typeperf-based, ~0.3s per cycle) |
| **All-Local Code Execution** | Code benchmarks run in Docker (`benchmax-sandbox` — `benchmax-sandbox`); clear error if Docker unavailable |
| **Official Benchmark Graders** | HumanEval/BigCodeBench via `safe_executor`, IFEval via official google-research checkers, BFCL via standalone AST checker |
| **Batch & Model Queue** | Run multiple benchmarks or multiple models in sequence with live ETA, accuracy comparison, and automatic load/unload |
| **Full Lifecycle Control** | Pause, resume, or halt any run or queue — state persisted to SQLite, resumes from exact position |
| **On-Demand Datasets** | Download full benchmark datasets from the UI — no manual fetching required |
| **Online Leaderboard** | Sync results to the public leaderboard and compare with the community |
| **Anti-Loop Protection** | Three-strategy repetition detection (exact substring, SequenceMatcher adjacency, fragment counting) prevents runaway model output |
| **Multimodal Vision** | MMMU-Pro sends images to vision models via the API (base64 PNG, 1,200 samples) |
| **CLI Tool** | 38-command wrapper for all API endpoints, useful for scripting and agent automation |

---

## Screenshots

> UI screenshots were removed from the repo — run the app and open `http://localhost:8000` to see the Connection, Run Benchmark, Hardware, and History tabs live.

---

## Benchmarks

| Benchmark | Category | Samples | Scoring Method |
|-----------|----------|---------|----------------|
| **HumanEval** | Code generation | 164 | `safe_executor` in Docker (`benchmax-sandbox`) |
| **MMLU-Pro** | Knowledge MCQ | 12,032 | Regex letter extraction (A–J) |
| **IFEval** | Instruction following | 541 | Official google-research `INSTRUCTION_DICT` classes |
| **AIME** | Math reasoning | 90 | Multi-strategy integer extraction |
| **BigCodeBench** | Code generation | 1,140 | `safe_executor` + unittest |
| **BigCodeBench-Hard** | Code generation (hard) | 148 | Hard subset |
| **BFCL** | Function calling | 4,696 | Standalone AST checker (`bfcl_checker.py`) |
| **UncensorBench** | Refusal behaviour | 150 | Keyword matching (UncensorBench project) |
| **Aider Polyglot** | Code editing | 225 | 6 languages (Python/JS/Java/Go/Rust/C++) in Docker (`benchmax-sandbox`) |
| **LongBench-v2** | Long-context QA | 503 | MCQ letter extraction (A–D) |
| **MMMU-Pro** | Multimodal vision | 1,200 | Image + text MCQ w/ base64 PNG |
| **LiveBench** | Meta-benchmark | 1,436 | 6 categories: MCQ, math, code, language, data, instruction |
| **LiveCodeBench** | Live code generation | 175 | `check_correctness_livecodebench()` |
| **BenchMax Personal** | Composite BMS | 100 | 5-dimension weighted score (BMS out of 100) |
| **BenchMax Lite** | All-round | 50 | 4 dimensions — Code/Knowledge/Math/Logic |
| **BenchMax Code** | Coding | 100 | 4 categories — Algorithms/Data Structures/Complexity/Theory |
| **BenchMax Reason** | Reasoning | 100 | Math 60 / Logic Puzzles 30 / Data Analysis 10 |
| **BenchMax Tectonic** | Multi-category | 300 | Coding/Logic/Instruction/Knowledge/Tool Calling |
| **Writing Speed Test** | Creative writing | 5 | ~300 tokens per prompt, always correct |
| **Coding Speed Test** | Code generation | 5 | ~300 tokens per prompt, always correct |
| **TruthfulQA** | Truthfulness MCQ | 817 | A/B multiple choice |
| **HellaSWAG** | Commonsense reasoning | 10,042 | MCQ sentence completion |
| **WinoGrande** | Coreference resolution | 1,267 | MCQ pronoun resolution |
| **ARC-Challenge** | Science reasoning | 1,172 | MCQ science exam |
| **CommonSenseQA** | Commonsense QA | 1,221 | MCQ commonsense knowledge |
| **Long Context Memory** | Memory recall | 1,542 | Exact-match from LOCOMO conversations |
| **NIAHS** | Needle-in-Haystack | 3 (5 depths each, multi-needle) | Hidden key retrieval at 10/25/50/75/90% |
| **GAIA** | Multi-Step Reasoning | ~165 | Multi-turn agentic with calculator + search tools |
| **Tau3-Airline** | Agentic Tool Use | 50 | Multi-turn airline customer-service agent (14 tools, simulated user, DB-state grading) |
| **BenchMax ToolCall** | Tool Use | 100 | Multi-call company planning (chains, parallel select-all, arg traps, diagnosis, state) |

Every benchmark accepts `quick_test=True` to load a mini dataset for fast validation (5 samples; NIAHS runs 3, Aider Polyglot 6 — one per language).

---

## Requirements

- **Python 3.11+** (for source builds) — or download the standalone .exe
- **Node.js 18+** (for frontend build only)
- **Docker Desktop** — only needed for the 5 code benchmarks (HumanEval, BigCodeBench ×2, LiveCodeBench, Aider Polyglot) via `benchmax-sandbox`; clear error if Docker not running
- **An API endpoint** — LM Studio (`localhost:1234`), Ollama (`localhost:11434`), OpenAI, Groq, etc.

---

## Quick Start

### Source Build

```powershell
git clone https://github.com/7amzaRando/BenchMax.git
cd BenchMax
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
cd frontend
npm install && npm run build
cd ..
.venv\Scripts\uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser. Connect to your API provider and start benchmarking.

> Without the frontend build, the API endpoints will work but the browser UI will not load.

### Standalone .EXE

```powershell
.\build.bat
# Output: dist\BenchMax.exe (~125MB, no Python needed)
```

### Docker Sandbox Image (for code benchmarks)

```powershell
# In the UI: Connection tab → "Build Docker Image" button
# Or via CLI:
py cli.py build-docker
```

This builds `benchmax-sandbox` (Python 3.11, Node 20, GCC, Java 17, Go 1.22, Rust 1.75) used by the 5 code benchmarks. All other benchmarks run host-local with no Docker.

---

## Architecture

```
Browser → http://localhost:8000
            │
            ▼
       FastAPI (backend/main.py)
         ├── GET /api/health + POST /api/shutdown
         ├── SPA serve at "/" → React frontend (frontend/dist/)
         └── REST API at /api/* → api.py (43 endpoints) → operations.py
               │
     ┌─────────┼──────────────────────────────┐
     ▼         ▼                              ▼
LM Studio   SQLite                     Docker benchmax-sandbox
:1234/v1    records/                   (--cap-drop ALL --network none
(httpx      benchmax.db                 --security-opt no-new-privileges)
streaming)  (SQLAlchemy, WAL)          5 code benchmarks: HumanEval,
                                       BigCodeBench ×2, LiveCodeBench,
                                       Aider Polyglot — clear error
                                        if Docker unavailable; 24 others
                                        run host-local with no Docker
```

### Single Run Flow

```
User clicks Start
  → React POSTs /api/run/start
  → trigger_run() creates Run row (PENDING)
  → daemon thread calls bench.run_evaluation()
    → for each sample:
        check Run.status
        → _check_repetition() on client
        → LMStudioClient.generate_completion()
        → extract code / parse answer
        → safe_executor.check_correctness_*()
        → write Result row
        → increment Run.current_index
  → React polls /api/run/{id}/status every 3s
  → renders UI
```

### Batch Flow (One Model, Multiple Benchmarks)

```
POST /api/batch/start
  → start_batch() creates batch UUID
  → chains benchmarks sequentially:
      benchmark_1 → benchmark_2 → ... → benchmark_N
  → each benchmark runs as a separate Run with shared batch_id
  → /api/batch/{batch_id} returns aggregated summary
```

### Model Queue Flow (Multiple Models × Benchmarks)

```
POST /api/model-queue/start
  → start_model_queue() creates queue
  → for each model:
      client.load_model(model_id)
      → run all M benchmarks sequentially
      → client.unload_model(model_id)
  → next model
  → /api/model-queue/active returns live queue state
```

### Anti-Loop Protection

Three-layer detection prevents runaway model loops:

1. **Client** (`_check_repetition()`): 3 strategies on a 1000-char sliding buffer
   - 200-char exact tail-in-body substring match
   - Adjacent SequenceMatcher (≥0.95 similarity)
   - 150-char fragment counting (≥3 occurrences)
   - Requires 3 consecutive detections to confirm a real loop
2. **Benchmark loop**: writes failed Result, increments index, continues to next sample
3. **UI**: poll injects "Repetition detected" warning

---

## Dashboard Tabs

| Tab | What it does |
|-----|-------------|
| **Connection** | API provider presets + endpoint config + API key + dataset installer + runtime downloader |
| **Run Benchmark** | Single-run, batch queue, or model queue with progress bar, ETA, live token stats |
| **Hardware** | Real-time CPU/RAM gauges + GPU/VRAM/temperature at 3s intervals (pause-able) |
| **History & Results** | Past runs, diff viewer, CSV/JSON export, batch comparison, token analysis, per-sample results, latency/TTFT/token distribution charts |
| **Leaderboard** | Local completed runs with sort/filter/delete + online leaderboard sync + model performance trend chart |

---

## CLI Tool

BenchMax includes a 38-command CLI (`cli.py`) for scripting and agent automation. Every REST API endpoint is accessible from the command line.

```powershell
# Start the server (auto-starts if not running)
py cli.py serve

# Connect to LM Studio
py cli.py connect --url http://127.0.0.1:1234

# Run a benchmark
py cli.py run --model deepseek-r1 --benchmark HumanEval --wait

# Get results as JSON
py cli.py results --run-id 1 --json
```

### All CLI Commands

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

**Global flags** (before subcommand):
- `--json` — machine-readable JSON output
- `--server URL` — override server address
- `--verbose` — debug HTTP traffic on stderr
- `--yes` — skip confirmation prompts

See [`AGENT_GUIDE.md`](AGENT_GUIDE.md) for detailed usage, examples, and agent workflows.

---

## REST API

The backend exposes 43 REST API endpoints under `/api/` (45 including `GET /api/health` and `POST /api/shutdown` in `backend/main.py`). Interactive documentation is available at **http://localhost:8000/docs** (Swagger UI) when the server is running.

### Core Endpoints

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

### RunRequest / BatchRequest / ModelQueueRequest

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

### Data & Export

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

### Leaderboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/leaderboard` | Get local leaderboard |
| `DELETE` | `/api/leaderboard/{id}` | Delete leaderboard entry |
| `POST` | `/api/leaderboard/clear` | Clear all history + leaderboard |
| `POST` | `/api/leaderboard/sync` | Sync to online leaderboard |
| `GET` | `/api/leaderboard/settings` | Get sync settings |
| `POST` | `/api/leaderboard/settings` | Set sync settings |

### Datasets & System

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
| `POST` | `/api/shutdown` | Shut down server (localhost only; `?token=` optional — wrong token → 401) |

### Error Responses

All endpoints return `{"detail": "Internal server error"}` with HTTP 500 on failure. Detailed error messages are logged server-side but not exposed to clients (prevents API key/path leakage).

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BENCHMAX_URL` | `http://127.0.0.1:8000` | Server URL for CLI commands (overridden by `--server`) |
| `HF_TOKEN` / `records/.hf_token` | (none) | HuggingFace token for gated datasets — set via `POST /api/hf-token` or `py cli.py hf-token --token` |
| `LOCALAPPDATA` | (Windows) `%LOCALAPPDATA%\BenchMax` | DB/config storage in .exe builds (`records/benchmax.db`) |
| `BENCHMAX_LOG_LEVEL` | `INFO` | Log level for `backend/logging_setup.py` (`DEBUG`/`INFO`/`WARNING`) |
| `BENCHMAX_JSON_LOGS` | (unset) | Set to `true` for JSON structured log output |
| `BENCHMAX_LOG_FILE` | (unset) | Write logs to this file path |
| `BENCHMAX_RELOAD` | (unset) | Set to `1` to opt into the `run.bat --reload` dev reloader |

---

## Tech Stack

| Technology | Role |
|------------|------|
| Python 3.11 | Backend logic and inference orchestration |
| FastAPI | REST API (43 endpoints: runs, batches, telemetry, export, leaderboard — 45 inc. health/shutdown) |
| React 19 + TypeScript | Dashboard UI (5 tabs, dark mode, real-time Recharts) |
| Vite | Frontend build tool |
| SQLAlchemy + SQLite | Run state, results, batch persistence (WAL mode) |
| httpx | Async HTTP streaming to LM Studio / API providers |
| Docker (`benchmax-sandbox`) | Isolated code execution sandbox (`--cap-drop ALL`, `--network none`) |
| psutil + GPUtil + typeperf | Hardware telemetry (CPU, RAM, GPU, VRAM, NVIDIA + AMD) |

---

## Project Structure

```
BenchMax/
├── backend/
│   ├── main.py              ← FastAPI app, SPA serve, /api/health + /api/shutdown (45 total with api.py)
│   ├── api.py               ← REST API router (43 endpoints)
│   ├── operations.py        ← Business logic: run, batch, queue, export, telemetry
│   ├── config.py            ← BENCHMARKS (29), DATASETS, PROVIDER_PRESETS (8)
│   ├── database.py          ← SQLAlchemy ORM (Run, Result) + WAL mode
│   ├── requirements.txt     ← Python dependencies
│   ├── benchmarks/          ← 29 benchmark implementations
│   │   ├── base.py          ← BaseBenchmark ABC: run_evaluation() loop
│   │   ├── humaneval.py     ← safe_executor code tests
│   │   ├── mmlu_pro.py      ← MCQ regex scoring
│   │   ├── ifeval.py        ← Official google-research IFEval checker
│   │   ├── bfcl.py          ← AST-based function call scoring
│   │   ├── aider_polyglot.py← 6-language code editing in Docker
│   │   ├── scoring.py       ← Shared MCQ/code/exact/free-form scorers
│   │   ├── mcq.py           ← GenericMCQBenchmark base class
│   │   └── ...              ← 20+ more benchmarks
│   ├── lm_studio/client.py  ← LMStudioClient: streaming, TTFT, TPS, anti-loop
│   ├── sandbox/
│   │   ├── safe_executor.py ← Cross-platform code execution sandbox
│   │   └── bfcl_checker.py  ← Standalone BFCL AST checker
│   └── telemetry/monitor.py ← CPU/RAM/GPU/VRAM monitoring
├── frontend/
│   ├── src/                 ← React/TypeScript source
│   ├── dist/                ← Built frontend (served by FastAPI)
│   └── package.json
├── data/                    ← Benchmark datasets (JSON)
├── scripts/                 ← Dataset fetch scripts
├── records/benchmax.db      ← SQLite database (auto-created)
├── cli.py                   ← CLI tool (38 commands)
├── run.bat                  ← Windows launcher
├── build.bat                ← PyInstaller .exe build script
└── .venv/                   ← Python virtual environment
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Docker unavailable` on HumanEval/BigCodeBench/LiveCodeBench/Aider | Docker Desktop not running or `benchmax-sandbox` image not built | Start Docker Desktop → `POST /api/docker/build` or Run Benchmark tab → `Build Docker Image` → verify `GET /api/docker/status` |
| `SPA 404` / blank page at `http://localhost:8000` | `frontend/dist/` not built | `cd frontend && npm install && npm run build` then restart `uvicorn` |
| `401` from LM Studio / OpenAI | Wrong `api_url` or missing `api_key` | Connection tab → check preset URL ends `/v1`, add API key for cloud providers |
| `Dataset not installed` dialog on run start | `data/*.json` missing | Datasets tab → `Install` / `Install All` or `POST /api/datasets/install-all` |
| `HF token required` for gated dataset | Gated HF dataset (rare) | `py cli.py hf-token --token hf_...` or `POST /api/hf-token` |
| `GPU temp N/A` on AMD | No WMI counter | Expected — load/VRAM still work via `typeperf`; temp is NVIDIA-only |
| Stream hangs on 64K NIAHS before first token | Long prompt processing (~170s at 64K) | Normal — `httpx` read timeout is 600s; check `avg_prompt_tps` after run |
| Shutdown does nothing / restarts | Server was started with `--reload` | By default `run.bat` does not use `--reload`; set `BENCHMAX_RELOAD=1` for dev. From localhost, `curl -X POST http://127.0.0.1:8000/api/shutdown` shuts down; wrong `?token=` still returns 401 |

Logs: `records/*.log` (JSON + human-readable, rotated) and `uvicorn` console. DB: `records/benchmax.db` (WAL mode, `engine.connect()`).

---

## License

Copyright (C) 2026 [Rando](https://github.com/7amzaRando)

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU Affero General Public License** as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

### Commercial License

If the AGPL v3 does not meet your needs, a **commercial license** is available. Contact [Rando](https://github.com/7amzaRando) for terms.

---

## Contact

**Author:** [Rando](https://github.com/7amzaRando)
**Sponsorship / Commercial Inquiries:** Reach out via GitHub

---

<div align="center">

**BenchMax** · [AGPL v3](LICENSE) · © 2026 Rando

</div>
