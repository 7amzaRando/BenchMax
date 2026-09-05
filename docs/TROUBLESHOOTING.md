# BenchMax Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Docker unavailable` on HumanEval/BigCodeBench/LiveCodeBench/Aider | Docker Desktop not running or `benchmax-sandbox` image not built | Start Docker Desktop → Connection tab → `Build Docker Image` (or `py cli.py build-docker`) → verify with `GET /api/docker/status` |
| `SPA 404` / blank page at `http://localhost:8000` | `frontend/dist/` not built | `cd frontend && npm install && npm run build`, then restart (`.\run.bat`) |
| `401` from LM Studio / OpenAI | Wrong `api_url` or missing `api_key` | Connection tab → check preset URL ends `/v1`; add API key for cloud providers |
| `Dataset not installed` dialog on run start | `data/*.json` missing | Connection tab → `Install` / `Install All`, or `POST /api/datasets/install-all` |
| `HF token required` for gated dataset | Gated HF dataset (rare) | `py cli.py hf-token --token hf_...` or `POST /api/hf-token` |
| `GPU temp N/A` on AMD | No WMI counter | Expected — load/VRAM still work via `typeperf`; temperature is NVIDIA-only |
| Stream hangs on NIAHS before first token | Long prompt processing | Normal — `httpx` read timeout is 600s; check `avg_prompt_tps` after the run. If prompt processing is the bottleneck, lower the NIAHS context-length slider or raise batch size in LM Studio settings (needs spare VRAM) |
| Shutdown does nothing / server restarts | Started with the dev reloader | By default `run.bat` does not use `--reload`; set `BENCHMAX_RELOAD=1` only for dev. From localhost: `curl -X POST http://127.0.0.1:8000/api/shutdown` |

Logs: `records/*.log` (JSON + human-readable, rotated) and the `uvicorn` console. DB: `records/benchmax.db` (WAL mode).
