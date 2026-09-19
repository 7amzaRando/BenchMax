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
    # Floor, not exact count — adding a benchmark must not break this test
    assert len(data["benchmarks"]) >= 30
    names = [b["name"] for b in data["benchmarks"]]
    for required in ("HumanEval", "MMLU-Pro", "TruthfulQA", "Tau3-Airline", "BenchMax ToolCall"):
        assert required in names


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
    assert data["runs"] == []  # isolated test DB starts empty (see conftest)


@pytest.mark.asyncio
async def test_runs_seeded_content(client):
    """Seed a run + result in the isolated DB and verify it surfaces via API."""
    from backend.database import Run, Result, get_db
    with get_db() as db:
        run = Run(model_name="audit-model", benchmark_name="MMLU-Pro",
                  status="COMPLETED", current_index=2, total_samples=2)
        db.add(run)
        db.commit()
        db.refresh(run)
        rid = run.id
        db.add(Result(run_id=rid, task_id="mmlu/0", prompt="q",
                      raw_response="B", correct=True,
                      elapsed_time=1.0, tps=10.0, ttft=0.2,
                      thinking_tokens=0, response_tokens=5, prompt_tokens=10))
        db.commit()
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert any(r.get("Model") == "audit-model" for r in runs)
    status = await client.get(f"/api/run/{rid}/status")
    assert status.status_code == 200
    body = status.json()
    assert body["model_name"] == "audit-model"
    assert body["samples_completed"] == 1
    assert body["samples_correct"] == 1


@pytest.mark.asyncio
async def test_run_status_unknown_404(client):
    resp = await client.get("/api/run/999999999/status")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trusted_card_unknown_404(client):
    resp = await client.get("/api/runs/999999999/card")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_leaderboard_empty(client):
    resp = await client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "leaderboard" in data
    assert isinstance(data["leaderboard"], list)


@pytest.mark.asyncio
async def test_poll(client):
    from unittest.mock import patch
    fake = {"cpu_percent": 10.0, "ram_used_gb": 4.0, "ram_total_gb": 16.0,
            "ram_percent": 25.0, "gpu_available": False, "gpu_name": "none",
            "gpu_load": 0.0, "vram_total_mb": 0, "vram_used_mb": 0, "vram_percent": 0.0}
    with patch("backend.api.get_system_metrics", return_value=fake), \
         patch("backend.ops.stats.get_system_metrics", return_value=fake):
        resp = await client.get("/api/poll")
    assert resp.status_code == 200
    data = resp.json()
    assert "telemetry" in data
    assert "run_progress" in data
    assert "batch_progress" in data
    telemetry = data["telemetry"]
    assert telemetry["cpu_percent"] == 10.0
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
    from unittest.mock import patch
    fake = {"cpu_percent": 10.0, "ram_used_gb": 4.0, "ram_total_gb": 16.0,
            "ram_percent": 25.0, "gpu_available": False, "gpu_name": "none",
            "gpu_load": 0.0, "vram_total_mb": 0, "vram_used_mb": 0, "vram_percent": 0.0}
    with patch("backend.api.get_system_metrics", return_value=fake):
        resp = await client.get("/api/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cpu_percent"] == 10.0
    assert data["ram_total_gb"] == 16.0
    assert "gpu_available" in data
    assert "vram_percent" in data
    assert isinstance(data["cpu_percent"], (int, float))
    assert isinstance(data["ram_total_gb"], (int, float))


@pytest.mark.asyncio
async def test_connect_refused(client):
    # No real socket: LMStudioClient._get_client() is patched to return a
    # client whose transport raises ConnectError, so this never touches
    # 127.0.0.1:19999. Intent preserved — a refused connection must surface
    # as a "Connection failed" status (HTTP 200), not raise.
    import httpx
    from unittest.mock import patch
    from backend.lm_studio.client import LMStudioClient

    def _refused(request):
        raise httpx.ConnectError("Connection refused (mocked, no real socket)", request=request)

    def _fake_get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(transport=httpx.MockTransport(_refused))
        return self._client

    with patch.object(LMStudioClient, "_get_client", _fake_get_client):
        resp = await client.post("/api/connect", json={"api_url": "http://127.0.0.1:19999/v1", "api_key": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "Connection failed" in data["status"] or "Error" in data["status"] or "error" in data["status"].lower()


@pytest.mark.asyncio
async def test_delete_runs_empty(client):
    # Empty / unparseable bulk deletes are client errors (400), not 200s.
    for path in ("/api/runs", "/api/leaderboard"):
        resp = await client.delete(path, params={"run_ids": ""})
        assert resp.status_code == 400
        assert "No valid run IDs" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_runs_invalid_ids(client):
    for path in ("/api/runs", "/api/leaderboard"):
        resp = await client.delete(path, params={"run_ids": "abc,!!"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "No valid run IDs provided."


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
