# BenchMax Configuration

## Requirements

- **Python 3.11+** (for source builds) — or use the standalone .exe (`.\build.bat` → `dist\BenchMax.exe`, no Python needed)
- **Node.js 18+** — for the one-time frontend build only (`cd frontend && npm install && npm run build`)
- **Docker Desktop** — only for the 5 code benchmarks (HumanEval, BigCodeBench ×2, LiveCodeBench, Aider Polyglot) via the `benchmax-sandbox` image (Python 3.11, Node 20, GCC, Java 17, Go 1.22, Rust 1.75). Build it from the Connection tab (**Build Docker Image**) or `py cli.py build-docker`. All other benchmarks run host-local with no Docker.
- **An API endpoint** — LM Studio (`localhost:1234`), Ollama (`localhost:11434`), OpenAI, Groq, etc. 8 provider presets ship in the Connection tab.

Without the frontend build, the API endpoints work but the browser UI will not load.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BENCHMAX_URL` | `http://127.0.0.1:8000` | Server URL for CLI commands (overridden by `--server`) |
| `BENCHMAX_HOST` | `127.0.0.1` | Host for `run.bat` (set to `0.0.0.0` for LAN access) |
| `BENCHMAX_PORT` | `8000` | Port for `run.bat` |
| `BENCHMAX_RELOAD` | `0` | Set to `1` to opt into the `run.bat` dev reloader |
| `HF_TOKEN` / `records/.hf_token` | (none) | HuggingFace token for gated datasets — set via `POST /api/hf-token` or `py cli.py hf-token --token` |
| `LOCALAPPDATA` | (Windows) `%LOCALAPPDATA%\BenchMax` | DB/config storage in .exe builds (`records/benchmax.db`) |
| `BENCHMAX_LOG_LEVEL` | `INFO` | Log level for `backend/logging_setup.py` (`DEBUG`/`INFO`/`WARNING`) |
| `BENCHMAX_JSON_LOGS` | (unset) | Set to `true` for JSON structured log output |
| `BENCHMAX_LOG_FILE` | (unset) | Write logs to this file path |

## Storage

- SQLite DB: `records/benchmax.db` (WAL mode) — runs, results, batch persistence.
- Logs: `records/*.log` (JSON + human-readable, rotated) plus `uvicorn` console output.
