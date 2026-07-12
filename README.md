<div align="center">

# BenchMax

### Local LLM Benchmarking Suite
**Evaluate any LLM against 21 standardized benchmarks — works with LM Studio, Ollama, OpenAI, and any OpenAI-compatible endpoint.**

<br>

<img src="https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
<img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" />
<img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
<br><br>

<img src="https://img.shields.io/badge/21-Benchmarks-8b5cf6?style=for-the-badge" />
<img src="https://img.shields.io/badge/8-API_Providers-06b6d4?style=for-the-badge" />
<img src="https://img.shields.io/badge/All--Local-22c55e?style=for-the-badge" />

</div>

---

<p align="center">
  <img src="Icon.png" alt="BenchMax Logo" width="80">
</p>

## Overview

BenchMax is a **free and open-source** LLM benchmarking platform under the **AGPL v3** license. Point it at any OpenAI-compatible API endpoint (local or cloud), select a benchmark, and get standardized scores across code generation, math reasoning, instruction following, function calling, safety, vision, and long-context tasks.

All benchmarks run **entirely locally** — no Docker required. Code benchmarks use `safe_executor` (multiprocessing + threading.Timer) for cross-platform timeouts, and Aider Polyglot uses portable language runtimes (Go, Rust, GCC, Java, Node.js).

Created by [**Rando**](https://github.com/7amzaRando).

---

## Screenshots

<p align="center">
  <strong>Hardware Monitor Tab</strong><br>
  <img src="Hardware-Monitor-Tab.png" alt="Hardware Tab" width="700">
</p>

<p align="center">
  <strong>History & Results — Charts & Stats</strong><br>
  <img src="Benchmark-Graph-Stats.png" alt="Benchmark Graphs and Statistics" width="700">
</p>

---

## Features

<table>
<tr>
<td width="50%">

#### 21 Benchmarks
HumanEval · MMLU-Pro · IFEval · AIME · BigCodeBench · BFCL · MCP-Bench · Safety · Aider Polyglot · LongBench-v2 · MMMU-Pro · LiveBench · BenchMax Personal · BenchMax Lite · BenchMax Code · BenchMax Reason · BenchMax Tectonic · Writing Speed Test · Coding Speed Test · TruthfulQA

</td>
<td width="50%">

#### 8 API Providers
LM Studio · Ollama · OpenAI · OpenRouter · Groq · DeepSeek · AIMLAPI · SiliconFlow — any OpenAI-compatible endpoint

</td>
</tr>
<tr>
<td width="50%">

#### Live Inference Metrics
TTFT, TPS, per-sample timing, token counts — streamed in real time via 3s polling

</td>
<td width="50%">

#### Hardware Telemetry
CPU, RAM, GPU load, VRAM, temperature — NVIDIA & AMD (typeperf-based, ~0.3s per cycle)

</td>
</tr>
<tr>
<td width="50%">

#### All-Local Code Execution
Code benchmarks run via multiprocessing + threading.Timer (no Docker). Aider Polyglot uses portable Go/Rust/GCC/Java/Node.js runtimes.

</td>
<td width="50%">

#### Official Benchmark Graders
HumanEval/BigCodeBench via `safe_executor`, IFEval via official google-research checkers, BFCL via standalone AST checker (no API deps)

</td>
</tr>
<tr>
<td width="50%">

#### Batch & Model Queue
Run multiple benchmarks or multiple models in sequence with live ETA, accuracy comparison, and automatic load/unload

</td>
<td width="50%">

#### Full Lifecycle Control
Pause, resume, or halt any run or queue — state persisted to SQLite, resumes from exact position

</td>
</tr>
<tr>
<td width="50%">

#### Multimodal Vision
MMMU-Pro sends images to vision models via the API (base64 PNG, 1,200 samples)

</td>
<td width="50%">

</td>
</tr>
<tr>
<td width="50%">

#### On-Demand Datasets
Download full benchmark datasets from the UI — no manual fetching required

</td>
<td width="50%">

#### Online Leaderboard
Sync results to the public leaderboard and compare with the community

</td>
</tr>
<tr>
<td width="50%">

#### Standalone .EXE
Build a single-file executable via PyInstaller (~125MB, no Python environment needed)

</td>
<td width="50%">

#### Anti-Loop Protection
Three-strategy repetition detection (exact substring, SequenceMatcher adjacency, fragment counting) prevents runaway model output

</td>
</tr>
<tr>
<td width="50%">

#### Temperature Toggle
Optionally omit temperature to use the provider's default, or set a custom value

</td>
<td width="50%">

</td>
</tr>
</table>

---

## Benchmarks

| Benchmark | Category | Samples | Scoring |
|---|---|---|---|
| **HumanEval** | Code generation | 164 | `safe_executor` (multiprocessing + threading.Timer) |
| **MMLU-Pro** | Knowledge MCQ | 12,032 | Regex letter extraction (A–J) |
| **IFEval** | Instruction following | 541 | Official google-research `INSTRUCTION_DICT` classes |
| **AIME** | Math reasoning | 90 | Multi-strategy integer extraction |
| **BigCodeBench** | Code generation | 1,140 | `safe_executor` + unittest |
| **BigCodeBench-Hard** | Code generation | 148 | Hard subset |
| **BFCL** | Function calling | 4,696 | Standalone AST checker (`bfcl_checker.py`) |
| **MCP-Bench** | MCP tool selection | 104 | Server + tool name + argument matching |
| **Safety** | Refusal behaviour | 450 | UncensorBench + OR-Bench keyword matching |
| **Aider Polyglot** | Code editing | 225 | 6 languages (Python/JS/Java/Go/Rust/C++) via subprocess + `.runtimes/` |
| **LongBench-v2** | Long-context QA | 503 | MCQ letter extraction (A–D) |
| **MMMU-Pro** | Multimodal vision | 1,200 | Image + text MCQ w/ base64 PNG |
| **LiveBench** | Meta-benchmark | 1,436 | 6 categories: MCQ, math, code, language, data, instruction |
| **BenchMax Personal** | Composite BMS | 100 | 5-dimension weighted score (BMS out of 100) |
| **BenchMax Lite** | All-round | 50 | 4 dimensions — Code/Knowledge/Math/Logic |
| **BenchMax Code** | Coding | 100 | 4 categories — Algorithms/Data Structures/Strings/Math |
| **BenchMax Reason** | Reasoning | 100 | Math/Logic/Data/Science |
| **BenchMax Tectonic** | Multi-category | 300 | Coding/Logic/Instruction/Knowledge/Tool Calling |
| **Writing Speed Test** | Creative writing | 5 | ~300 tokens per prompt, always correct |
| **Coding Speed Test** | Code generation | 5 | ~300 tokens per prompt, always correct |
| **TruthfulQA** | Truthfulness MCQ | 817 | A/B multiple choice |

---

## Dashboard Tabs

| Tab | What it does |
|---|---|
| **Connection** | API provider presets + endpoint config + API key + dataset installer + runtime downloader |
| **Run Benchmark** | Single-run, batch queue, or model queue with progress bar, ETA, live token stats |
| **Hardware** | Real-time CPU/RAM gauges + GPU/VRAM/temperature at 3s intervals (pause-able) |
| **History & Results** | Past runs, diff viewer, CSV/JSON export, batch comparison, token analysis, per-sample results, latency/TTFT/token distribution charts |
| **Leaderboard** | Local completed runs with sort/filter/delete + online leaderboard sync + model performance trend chart |

---

## Requirements

- **Python 3.11+** (for source builds) — or download the standalone .exe
- **An API endpoint** — LM Studio (`localhost:1234`), Ollama (`localhost:11434`), OpenAI, Groq, etc.
- **Optional: Portable runtimes** for Aider Polyglot (Go, Rust, GCC, Java, Node.js) — downloadable from the UI

---

## Quick Start

### Source Build

```powershell
# Requires: Python 3.11+, Node.js 18+
git clone https://github.com/7amzaRando/BenchMax.git
cd BenchMax
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
cd frontend
npm install && npm run build
cd ..
.venv\Scripts\uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

> **Note:** Without the frontend build, the API endpoints will work but the browser UI at `http://localhost:8000` will not load. The frontend build step is required for the full SPA experience.

### Download Portable Runtimes (for Aider Polyglot)

```powershell
# In the UI: Connection tab → "Download Runtimes" button
# Or via script:
.venv\Scripts\python scripts\setup_runtimes.py
```

### Standalone .EXE

```powershell
.\build.bat
# Output: dist\BenchMax.exe (~84MB, no Python needed)
```

Open **http://localhost:8000** in your browser. Connect to your API provider and start benchmarking.

---

## Architecture

```
Browser → http://localhost:8000
            │
            ▼
       FastAPI (backend/main.py)
         ├── GET /api/health
         ├── SPA serve at "/" → React frontend (frontend/dist/)
         └── REST API at /api/* → api.py → operations.py
               │
     ┌─────────┼──────────────────────────┐
     ▼         ▼                          ▼
LM Studio   SQLite                 safe_executor
:1234/v1    records/               (multiprocessing
(httpx      benchmax.db            + threading.Timer)
streaming)  (SQLAlchemy)           for code benchmarks
                                       │
                                  .runtimes/
                                  (Go, Rust, GCC,
                                   Java, Node.js)
```

**Data flow:** User clicks Start → React POSTs `/api/run/start` → `trigger_run()` creates `Run` row (PENDING) → daemon thread calls `bench.run_evaluation()` → for each sample: check Run.status → `_check_repetition()` on client → `LMStudioClient.generate_completion()` → extract code → `safe_executor.check_correctness_*()` → write `Result` row → increment `Run.current_index`. React polls `/api/run/{id}/status` every 3s → renders UI.

**Anti-loop Protection:** Three-layer detection (v2 — reliable). **Client** (`_check_repetition()`): (A) 200-char exact tail-in-body substring match, (B) adjacent SequenceMatcher(autojunk=False, ≥0.95), (C) 100-char fragment counting (≥5 occurrences). Stream aborted immediately via `break`. **Benchmark loop**: writes failed Result, increments index, continues. **UI**: poll injects "Repetition detected" warning.

---

## Tech Stack

| Technology | Role |
|---|---|
| Python 3.11 | Backend logic and inference orchestration |
| FastAPI | REST API (35+ endpoints: runs, batches, telemetry, export, leaderboard) |
| React 19 + TypeScript | Dashboard UI (5 tabs, dark mode, real-time Recharts) |
| Vite | Frontend build tool |
| SQLAlchemy + SQLite | Run state, results, batch persistence (WAL mode) |
| httpx | Async HTTP streaming to LM Studio / API providers |
| multiprocessing + threading.Timer | Cross-platform code execution sandbox (no Docker) |
| psutil + GPUtil + typeperf | Hardware telemetry (CPU, RAM, GPU, VRAM, NVIDIA + AMD) |

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
