import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["app"] == "BenchMax"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_benchmarks(client):
    resp = await client.get("/api/benchmarks")
    assert resp.status_code == 200
    data = resp.json()
    assert "benchmarks" in data
    assert isinstance(data["benchmarks"], list)
    assert len(data["benchmarks"]) == 30
    names = [b["name"] for b in data["benchmarks"]]
    assert "HumanEval" in names
    assert "MMLU-Pro" in names
    assert "TruthfulQA" in names
    assert "Tau3-Airline" in names
    assert "BenchMax ToolCall" in names


@pytest.mark.asyncio
async def test_datasets(client):
    resp = await client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert "datasets" in data
    assert isinstance(data["datasets"], list)
    assert len(data["datasets"]) > 0
    entry = data["datasets"][0]
    assert "Benchmark" in entry
    assert "Installed" in entry


@pytest.mark.asyncio
async def test_runs_empty(client):
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert isinstance(data["runs"], list)


@pytest.mark.asyncio
async def test_leaderboard_empty(client):
    resp = await client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "leaderboard" in data
    assert isinstance(data["leaderboard"], list)


@pytest.mark.asyncio
async def test_poll(client):
    resp = await client.get("/api/poll")
    assert resp.status_code == 200
    data = resp.json()
    assert "telemetry" in data
    assert "run_progress" in data
    assert "batch_progress" in data
    telemetry = data["telemetry"]
    assert "cpu_percent" in telemetry
    assert "ram_used_gb" in telemetry
    assert "gpu_available" in telemetry
    run_progress = data["run_progress"]
    assert "progress" in run_progress
    assert "status_md" in run_progress
    assert "accuracy" in run_progress
    batch_progress = data["batch_progress"]
    assert "progress" in batch_progress
    assert "completed" in batch_progress
    assert "total" in batch_progress


@pytest.mark.asyncio
async def test_telemetry(client):
    resp = await client.get("/api/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu_percent" in data
    assert "ram_used_gb" in data
    assert "ram_total_gb" in data
    assert "ram_percent" in data
    assert "gpu_available" in data
    assert "gpu_name" in data
    assert "gpu_load" in data
    assert "vram_total_mb" in data
    assert "vram_used_mb" in data
    assert "vram_percent" in data
    assert isinstance(data["cpu_percent"], (int, float))
    assert isinstance(data["ram_total_gb"], (int, float))


@pytest.mark.asyncio
async def test_connect_refused(client):
    resp = await client.post("/api/connect", json={"api_url": "http://127.0.0.1:19999/v1", "api_key": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "Connection failed" in data["status"] or "Error" in data["status"] or "error" in data["status"].lower()


def test_sanitize_for_json_replaces_non_finite():
    import json
    import math
    from backend.api import sanitize_for_json, SafeJSONResponse
    payload = {
        "avg_tps": float("nan"),
        "avg_ttft": float("inf"),
        "neg": float("-inf"),
        "nested": [{"v": float("nan")}, {"ok": 1.5}],
        "name": "x",
    }
    clean = sanitize_for_json(payload)
    # strict re-serialization must not raise
    json.dumps(clean, allow_nan=False)
    assert clean["avg_tps"] == 0.0
    assert clean["avg_ttft"] == 0.0
    assert clean["neg"] == 0.0
    assert clean["nested"][0]["v"] == 0.0
    assert clean["nested"][1]["ok"] == 1.5
    assert clean["name"] == "x"
    # render boundary never crashes on NaN payloads (regression:
    # "ValueError: Out of range float values are not JSON compliant")
    body = SafeJSONResponse(payload).body
    json.dumps(json.loads(body), allow_nan=False)
    assert math.isfinite(json.loads(body)["avg_tps"])
