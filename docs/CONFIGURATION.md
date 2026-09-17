# BenchMax Configuration

## Requirements

- **Python 3.11+** (for source builds) — or use the standalone .exe (`.\build.bat` → `dist\BenchMax.exe`, no Python needed; release tags also auto-build it via GitHub Actions, see **GitHub Releases**)
- **Node.js 18+** — for the one-time frontend build only (`cd frontend && npm install && npm run build`)
- **Docker Desktop** — only for the 5 code benchmarks (HumanEval, BigCodeBench ×2, LiveCodeBench, Aider Polyglot) via the `benchmax-sandbox` image (Python 3.11, Node 20, GCC, Java 17, Go 1.22, Rust 1.75), plus LiveBench's coding questions. Build it from the Connection tab (**Build Docker Image**) or `py cli.py build-docker`. Everything else runs host-local with no Docker — without it, LiveBench coding questions are skipped (other categories unaffected).
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

## LAN access & password

By default BenchMax listens on `127.0.0.1` — only your own PC can reach it, and no login is needed. To share it on your local network (e.g. open it on your phone):

1. On the server machine, set a LAN password: `py cli.py set-password` (you'll be prompted securely).
2. Start the server shared: `py cli.py serve --host 0.0.0.0` (or set `BENCHMAX_HOST=0.0.0.0` before `run.bat`).
3. Visitors on the network open `http://<your-pc-ip>:8000` and see a login screen — nothing loads until they enter the password. Your own browser on the server machine keeps working with no login.

Notes:

- The password is stored as a one-way hash in `records/.lan_password` (never plaintext). Changing it logs out all LAN sessions immediately.
- Forgot the password? Stop the server, delete `records/.lan_password`, start it again, and run `py cli.py set-password` to choose a new one.
- Only share on networks you trust (home WiFi). The connection is plain HTTP — the password keeps strangers out, but don't expose it to the internet.

## Concurrency & single-process

BenchMax runs up to 4 benchmark runs at once (`MAX_CONCURRENT_RUNS` in `backend/ops/state.py`). Starting a 5th returns HTTP 429 and saves the run as PENDING so it can be resumed later. Batch/queue/halt state lives in process memory — always run a single worker (never `uvicorn --workers 4`); `BENCHMAX_WORKERS` set to anything but `1` logs a warning at startup.

## Storage

- SQLite DB: `records/benchmax.db` (WAL mode) — runs, results, batch persistence.
- Logs: `records/*.log` (JSON + human-readable, rotated) plus `uvicorn` console output.

## Backup & restore

Everything BenchMax knows lives in `records/benchmax.db` (source builds) or `%LOCALAPPDATA%\BenchMax\benchmax.db` (.exe builds). To back up: stop the server (`POST /api/shutdown` or Ctrl+C in the terminal), then copy `benchmax.db` plus the `-wal` / `-shm` sidecar files if present. To restore: stop the server, copy the files back, restart. Copying while the server is running can produce a corrupt backup, so always stop it first. There is no separate migration step — schema upgrades apply automatically on startup.
