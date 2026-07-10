# BenchMax v1.0 Release Notes — "Metamorphic"

> This is a **major** release: the entire UI layer was replaced and the backend was restructured into a REST API. A UI framework upgrade is a breaking (MAJOR) change, hence `v1.0`.

---

## Breaking Changes

- **Gradio UI removed entirely.** The old Python dashboard was deleted. The app is now a single-page React app served from `frontend/dist/`. Any direct Gradio integration, callbacks, or custom theme code will no longer work.
- **New REST API surface.** All operations moved behind a REST API (30+ endpoints, e.g. `POST /api/run/start`, `GET /api/run/{id}/status`, `GET /api/poll`). Old UI callback functions are gone; callers must switch to the HTTP API.
- **Business logic relocated.** Run/batch/export/telemetry logic now lives in `backend/operations.py` and benchmark/provider definitions in `backend/config.py`. Importing from the old dashboard module will fail.
- **Benchmarks re-register in `config.py`.** Any custom benchmark relying on the old dashboard registration chain must be re-registered in `config.py` + `operations.py`.
- **Personal BMS scoring changed.** Composite BMS redesigned from **7 dimensions (3 dead → max score 65/100)** to **5 active dimensions** (Code 25, Knowledge 15, Instruction 15, Math 25, Logic 20 = 100). Historical Personal scores from v1.x are not comparable to v1.0 scores.
- **Max tokens defaults changed.** Slider default is now **8192** (max 32768); previously the maximum was 64k.
- **Docker experiment harness changed.** Aider Polyglot no longer shells out via raw `docker run` or pulls images from Docker Hub; it uses the local `benchmax-*` images (`benchmax-node/java/gcc/go/rust` plus `benchmax-python`) through the executor with container reuse. Building those images is now required for non-Python Aider Polyglot.

---

## New Features

- **React 19 + TypeScript + Vite frontend.** Dark/light mode (slate `#0f172a` dark), Recharts visualizations, Radix UI components. 5 tabs: Connection, Run Benchmark, Hardware, History & Results, Leaderboard.
- **TruthfulQA benchmark (21st benchmark).** 817-question A/B multiple-choice truthfulness evaluation.
- **Multi-Model Queue.** Load → run all benchmarks → unload → next model, fully automated, with a 3-mode UI selector (Single / Batch / Model Queue).
- **Docker build streaming.** Background build with SSE progress (emits `log`/`image`/`done` events), scrollable log UI, and per-image auto-dismissing toasts.
- **REST API (30+ endpoints).** Connect, run, batch, model-queue, export, telemetry, datasets, leaderboard, diff, comparison, poll.
- **Sortable + filterable leaderboard.** Click any column header to sort; text filter box; emojis replaced with `1st`/`2nd`/`3rd` styled text.
- **Per-benchmark dataset Install buttons** in the Connection tab; connection errors now propagate to the UI instead of showing "Not connected".
- **Aider Polyglot offline.** Five new Dockerfiles with pre-installed deps (Jest, JUnit+AssertJ, Catch2) — no runtime downloads.
- **Generate Diff now works for all 21 benchmarks** (generalized via benchmark instantiation + dataset lookup); previously HumanEval-only.

---

## Bug Fixes

**Anti-loop detection (the big one):**
- Root cause of v1.x unreliability found: the old algorithm compared unequal-length strings via `SequenceMatcher` (50-char window vs ~170-char context), capping max ratio at ~0.45 — permanently below the 0.7 threshold, so detection was *mathematically impossible* for responses >140 chars.
- Rewritten with 3 strategies on a 1000-char buffer: (A) 120-char exact tail-in-body substring, (B) equal-length adjacent `SequenceMatcher(autojunk=False, ≥0.85)`, (C) 60-char fragment counting (≥3 occurrences). Stream aborts immediately via `break`. Now considered reliable.

**Full benchmark bug sweep (65+ fixes across 20+ files):**
- CRITICAL: HumanEval double-colon syntax error (body-only responses always invalid Python); MCP-Bench missing `import re` (crash on code-fence responses).
- False-positive answer extraction: "I"/"A" filtered from prose pronouns across 3 MCQ benchmarks; MCQ scoring changed from first-match to last-match regex in 4 files.
- Empty-answer always-True scoring fixed in personal/lite/code/reason/tectonic.
- IFEval list-vs-string crash fixed; Safety italic regex corrected to preserve inner text.
- Docker stderr loss fixed (combined stdout/stderr in error output).
- Lite/Code/Reason/Personal/Tectonic now delegate to the base run loop for standard pause/halt/repetition flow.

**Infrastructure / system:**
- **GPU/VRAM monitoring fix (AMD).** Root cause: telemetry used `Get-Counter -SampleInterval 0` (invalid on Windows, min is 1) → counters always empty → GPU load/VRAM permanently 0. Replaced with `typeperf -sc 1 -si 0` (~0.3s vs ~1.7s); now returns real values on AMD RX 7600 XT.
- **Docker executor rewrite.** Broken `create()`+`exec_run()` → working `run(detach=True)`+`wait()`+`logs()`, plus a reusable-container path (`sleep infinity` + `exec_run` per sample) to avoid per-sample container creation overhead.
- **Dockerfile fix.** Removed non-existent `USER appuser`; fixed `COPY package.json` path; fixed optimize Dockerfile (empty apt-get, deprecated flags, broken COPY).
- **Diff route fix.** Route changed so multi-segment task IDs like `BigCodeBench-Hard/3` are captured (was 404).
- **Leaderboard** date sort fixed (real date compare); category scores "general" fix (passes benchmark name fallback).
- **Results Analyzer removed** from History & Results tab (redundant inline card).

**Performance optimizations:**
- N+1 query fixes via joined-loaded results.
- Docker container reuse (one container per benchmark via `sleep infinity`).
- Persistent `httpx` async client per instance.
- DB write batching (commit every 50 samples).
- Dataset caching (class-level dict).
- Docker image trim: `benchmax-python` 2.74GB (61 pkgs) → ~1.1GB (32 pkgs), 99.3% BigCodeBench coverage. The other sandbox images (`benchmax-node/java/gcc/go/rust`) remain in use by Aider Polyglot.

---

## Other / Improvements

- **Tech stack:** React 19, TypeScript, Vite, Tailwind CSS, Recharts, Radix UI (frontend); backend remains FastAPI + SQLAlchemy + SQLite.
- **20 → 21 benchmarks** (Community count 5 → 6).
- **Frontend poll interval** reduced server load: 1s → 3s; GPU/PowerShell telemetry cached with 2s TTL (CPU/RAM always fresh).
- **Config centralized** in `backend/config.py` (`BENCHMARKS`, `DATASETS`, `PROVIDER_PRESETS`, `DOCKER_BENCHMARKS`).
- **PyInstaller** path updated (`benchmax_server.py`, `benchmax.spec`, `build.bat`, `start.py`).
- **Known issues carried over:** TTFT & TPS Distribution graphs still broken in History & Results.

---

## Upgrade Notes

1. Clone the repo, then build the frontend: `cd frontend && npm install && npm run build` (frontend must be built before the backend serves it).
2. Build the local `benchmax-python` image via the UI "Build Local Images" button (or the build script) — required for code benchmarks.
3. The `.exe` build now bundles both the Python backend and the built `frontend/dist`.
4. Historical run/result rows remain valid, but Personal BMS scores from v1.x are not comparable due to the 7→5 dimension redesign.
