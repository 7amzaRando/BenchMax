"""Architecture-audit regression tests (no Docker / no LM Studio needed).

Pins the audit fixes: shared state single-source, 201 creates, 404/409/400
mappings, canonical DELETE /api/runs, per-run live-turn slots, run-slot
semaphore, shared poll builder, public Docker probes.
"""
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _seed_run(status="COMPLETED", benchmark="MMLU-Pro", model="m"):
    from backend.database import Run, get_db
    with get_db() as db:
        run = Run(model_name=model, benchmark_name=benchmark, status=status,
                  current_index=1, total_samples=1,
                  parameters='{"quick_test": true}')
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id


class TestSharedState:
    def test_operations_reexports_state_objects(self):
        import backend.operations as ops
        import backend.ops.state as st
        assert ops._batch_lock is st._batch_lock
        assert ops._model_queue_lock is st._model_queue_lock
        assert ops._halt_events is st._halt_events
        assert ops.telemetry_history is st.telemetry_history
        assert ops._active_threads is st._active_threads

    def test_no_local_state_duplicates(self):
        import inspect
        import backend.operations as ops
        src = inspect.getsource(ops)
        assert "_halt_events: dict" not in src
        assert "_model_queue_state: dict = {" not in src


class TestStatusCodes:
    @pytest.mark.asyncio
    async def test_run_start_returns_201(self, client):
        with patch("backend.api.trigger_run", return_value=(1, "Run 1 started.")):
            resp = await client.post("/api/run/start", json={
                "model": "m", "benchmark": "MMLU-Pro",
                "api_url": "http://127.0.0.1:1234/v1"})
        assert resp.status_code == 201
        assert resp.json()["run_id"] == 1

    @pytest.mark.asyncio
    async def test_batch_start_returns_201(self, client):
        import pandas as pd
        with patch("backend.api.start_batch",
                   return_value=(1, "b" * 36, "ok", pd.DataFrame(), "b" * 8)):
            resp = await client.post("/api/batch/start", json={
                "model": "m", "benchmarks": ["MMLU-Pro"],
                "api_url": "http://127.0.0.1:1234/v1"})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_pause_missing_is_404(self, client):
        resp = await client.post("/api/run/999999999/pause")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_pause_wrong_status_is_409(self, client):
        rid = _seed_run(status="COMPLETED")
        resp = await client.post(f"/api/run/{rid}/pause")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_notes_missing_is_404(self, client):
        resp = await client.patch("/api/runs/999999999/notes",
                                  json={"notes": "hi"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_missing_is_404(self, client):
        resp = await client.get("/api/export/runs/999999999")
        assert resp.status_code == 404


class TestCanonicalDelete:
    @pytest.mark.asyncio
    async def test_delete_runs_canonical(self, client):
        from backend.database import Run, get_db
        rid = _seed_run()
        resp = await client.delete("/api/runs", params={"run_ids": str(rid)})
        assert resp.status_code == 200
        assert str(rid) in resp.json()["status"]
        with get_db() as db:
            assert db.query(Run).filter(Run.id == rid).first() is None


class TestLiveTurnPerRun:
    def test_slots_are_per_run(self):
        from backend.benchmarks.multi_turn_base import (
            get_live_turn_state, _set_live_turn, _clear_live_turn)
        _clear_live_turn()
        _set_live_turn(1, 1, 3, 0.1)
        _set_live_turn(2, 2, 5, 0.2)
        assert get_live_turn_state(1)["turn"] == 1
        assert get_live_turn_state(2)["turn"] == 2
        _clear_live_turn(1)
        assert get_live_turn_state(1) == {}
        assert get_live_turn_state(2)["turn"] == 2
        _clear_live_turn()
        assert get_live_turn_state() == {}


class TestRunSlots:
    def test_busy_when_saturated(self):
        import backend.operations as ops
        # Drain all slots, then a start must refuse without spawning threads.
        acquired = []
        try:
            for _ in range(ops.MAX_CONCURRENT_RUNS):
                assert ops._run_slots.acquire(blocking=False)
                acquired.append(True)
            with patch.object(ops.threading, "Thread") as thr:
                assert ops._start_benchmark_thread(
                    123456, "http://127.0.0.1:1234/v1", "", 0.0, 8, "") is None
                thr.assert_not_called()
        finally:
            for _ in acquired:
                ops._run_slots.release()


class TestPollBuilder:
    def test_poll_and_stream_share_shape(self):
        import pandas as pd
        from backend.operations import build_poll_payload
        result = {
            "metrics": {"cpu_percent": 1.0, "ram_used_gb": 2.0, "ram_total_gb": 8.0,
                        "ram_percent": 25.0, "gpu_available": False, "gpu_name": "n/a",
                        "gpu_load": 0.0, "vram_total_mb": 0, "vram_used_mb": 0,
                        "vram_percent": 0.0},
            "prog_val": 0.5, "status_md": "x", "active_task": "t",
            "avg_tps": 1.0, "avg_ttft": 0.1, "accuracy": "50%",
            "token_stats": "tok",
            "batch_prog_val": 0.0, "batch_status_md": "", "batch_eta_str": "",
            "batch_summary_df": pd.DataFrame(), "batch_id_val": "",
            "batch_done": 0, "batch_total": 0, "batch_current_name": "",
            "active_run_override": None, "live_turn": None,
        }
        payload = build_poll_payload(result)
        assert set(payload) == {"telemetry", "run_progress", "batch_progress",
                                "active_run_override", "live_turn"}
        assert payload["batch_progress"]["summary"] == []


class TestDockerProbes:
    def test_public_probes_exist(self):
        from backend.sandbox.docker_executor import (
            is_docker_available, is_sandbox_usable)
        assert isinstance(is_docker_available(), bool)
        assert isinstance(is_sandbox_usable(), bool)

    def test_livebench_uses_public_probe(self):
        import inspect
        from backend.benchmarks import livebench
        src = inspect.getsource(livebench.LiveBenchBenchmark._docker_usable)
        assert "is_sandbox_usable" in src
        assert "_docker_available" not in src


class TestServiceLayer:
    def test_run_status_service(self):
        from backend.operations import get_run_status
        from backend.ops.errors import RunNotFoundError
        rid = _seed_run()
        body = get_run_status(rid)
        assert body["run_id"] == rid
        assert body["model_name"] == "audit-model" or body["model_name"] == "m"
        try:
            get_run_status(999999999)
            raised = False
        except RunNotFoundError:
            raised = True
        assert raised

    def test_update_notes_service(self):
        from backend.operations import update_run_notes
        rid = _seed_run()
        assert update_run_notes(rid, "hello") == "hello"
