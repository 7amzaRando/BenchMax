#!/usr/bin/env python3
"""BenchMax MCP server — exposes benchmarking as Model Context Protocol tools.

Stdio mode (local apps: Claude Desktop, Cursor, VS Code, OpenCode)::

    .venv\\Scripts\\python mcp_server.py

Remote mode is served by the BenchMax app itself at ``/mcp``
(Streamable HTTP) once the server is running — no extra process.

Requires the BenchMax server (run.bat or ``uvicorn backend.main:app``).
Set BENCHMAX_URL to point elsewhere; BENCHMAX_TOKEN for LAN Bearer auth.
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("benchmax")

BASE = os.environ.get("BENCHMAX_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ.get("BENCHMAX_TOKEN", "")


def _headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def _api(method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    with httpx.Client(base_url=BASE, timeout=60.0, headers=_headers()) as c:
        r = c.request(method, path, json=body, params=params)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {"result": data}


@mcp.tool()
def list_benchmarks() -> dict:
    """List all 30 BenchMax benchmarks with descriptions."""
    return _api("GET", "/api/benchmarks")


@mcp.tool()
def run_benchmark(model: str, benchmark: str, quick_test: bool = True,
                  max_tokens: int = 2048, temperature: float | None = None) -> dict:
    """Start a benchmark run. Returns run_id — poll get_status, don't block."""
    body: dict = {"model": model, "benchmark": benchmark,
                  "quick_test": quick_test, "max_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    return _api("POST", "/api/run/start", body)


@mcp.tool()
def run_batch(model: str, benchmarks: list[str], quick_test: bool = True,
              max_tokens: int = 2048) -> dict:
    """Run several benchmarks on one model. Returns batch_id."""
    return _api("POST", "/api/batch/start",
                {"model": model, "benchmarks": benchmarks,
                 "quick_test": quick_test, "max_tokens": max_tokens})


@mcp.tool()
def get_status(run_id: int) -> dict:
    """Check run progress: status, accuracy, samples done, TPS."""
    return _api("GET", f"/api/run/{run_id}/status")


@mcp.tool()
def control_run(run_id: int, action: str) -> dict:
    """Pause, resume, or halt a run. action is pause|resume|halt."""
    action = action.lower()
    if action not in ("pause", "resume", "halt"):
        return {"error": "action must be pause, resume, or halt"}
    if action == "resume":
        return _api("POST", f"/api/run/{run_id}/resume")
    return _api("POST", f"/api/run/{run_id}/{action}")


@mcp.tool()
def get_results(run_id: int) -> dict:
    """Full run results: summary stats plus per-sample pass/fail."""
    return _api("GET", f"/api/runs/{run_id}")


@mcp.tool()
def list_history(limit: int = 20, status: str = "") -> dict:
    """List past runs, newest first. status filters e.g. COMPLETED."""
    params: dict = {"limit": max(1, min(limit, 500))}
    return _api("GET", "/api/runs", params=params)


@mcp.tool()
def compare_runs(run_ids: str) -> dict:
    """Compare runs head-to-head. run_ids is comma-separated, e.g. '12,13'."""
    return _api("GET", "/api/comparison", params={"run_ids": run_ids})


@mcp.tool()
def get_telemetry() -> dict:
    """Live CPU/RAM/GPU/VRAM stats for the benchmark host."""
    return _api("GET", "/api/telemetry")


@mcp.tool()
def set_endpoint(url: str) -> dict:
    """Set the default LLM provider endpoint (e.g. http://127.0.0.1:1234/v1).
    Validated, probed, and saved; runs without an explicit api_url use it.
    Models live in the provider (LM Studio/Ollama) — there is no separate
    model registry, so this plus list_models is the full setup path."""
    return _api("POST", "/api/provider", {"url": url})


@mcp.tool()
def get_endpoint() -> dict:
    """Show the saved default provider endpoint."""
    return _api("GET", "/api/provider")


@mcp.tool()
def list_models(api_url: str = "") -> dict:
    """Model IDs currently loaded at the provider (default endpoint unless
    api_url is given). Run these names via run_benchmark."""
    params = {"api_url": api_url} if api_url else None
    return _api("GET", "/api/models", params=params)


@mcp.tool()
def check_endpoint_health(api_url: str = "") -> dict:
    """Is the LLM backend serving? Times the provider and counts loaded
    models. Call before a big run instead of burning it on a dead backend."""
    params = {"api_url": api_url} if api_url else None
    return _api("GET", "/api/provider/health", params=params)


@mcp.tool()
def register_webhook(url: str) -> dict:
    """POST this URL (JSON) whenever a run hits COMPLETED/FAILED/HALTED,
    so you don't have to poll get_status. Returns an id."""
    return _api("POST", "/api/webhooks", {"url": url})


@mcp.tool()
def list_webhooks() -> dict:
    """List registered run-completion webhooks."""
    return _api("GET", "/api/webhooks")


@mcp.tool()
def delete_webhook(hook_id: str) -> dict:
    """Remove a run-completion webhook by id."""
    with httpx.Client(base_url=BASE, timeout=30.0, headers=_headers()) as c:
        r = c.delete(f"/api/webhooks/{hook_id}")
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    mcp.run()
