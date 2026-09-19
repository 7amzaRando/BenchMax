"""Model-queue loop coverage: skip / per-model failure / unload failure / halt.

Calls ``_run_model_queue_in_thread`` directly (via the ``backend.operations``
facade) with a mocked client + FakeBench-style benchmark — no threads are
spawned and no LLM calls are made. ``time.sleep`` is stubbed for speed.
"""
import uuid
from unittest.mock import patch

API_URL = "http://127.0.0.1:1234/v1"


class _FakeClient:
    """Stands in for LMStudioClient: records load/unload, never touches network."""

    def __init__(self, unload_fail=False):
        self.loaded = []
        self.unloaded = []
        self.unload_fail = unload_fail
        self._rep_disabled = False

    async def load_model(self, model_id):
        self.loaded.append(model_id)
        return {"status_code": 200, "body": "ok"}

    async def unload_model(self, model_id):
        self.unloaded.append(model_id)
        if self.unload_fail:
            raise RuntimeError("unload boom")
        return {"status_code": 200}

    async def aclose(self):
        return None


def _make_fake_bench(behaviors, calls):
    """Build a FakeBench class driven by per-model behaviors.

    behaviors: {model_name: "ok" | "fail" | "skip" | "halt"}.
    "fail" raises inside run_evaluation (loop must mark FAILED + continue).
    "skip" sets the queue skip flag (loop must advance to the next model).
    "halt" calls the facade halt_model_queue (loop must stop the queue).
    """

    class FakeBench:
        def __init__(self, db, client, quick_test=False):
            pass

        async def run_evaluation(self, run_id, params):
            from backend.database import Run, get_db

            with get_db() as db:
                rec = db.query(Run).filter(Run.id == run_id).first()
                model = rec.model_name if rec else "?"
            calls.append(model)
            beh = behaviors.get(model, "ok")
            if beh == "skip":
                from backend.operations import _model_queue_lock, _model_queue_state

                with _model_queue_lock:
                    _model_queue_state["skip_model"] = True
            elif beh == "halt":
                from backend.operations import halt_model_queue

                halt_model_queue()
            elif beh == "fail":
                raise RuntimeError("boom-fake-bench")
            if beh == "halt":
                return None
            with get_db() as db2:
                rec2 = db2.query(Run).filter(Run.id == run_id).first()
                if rec2 is not None:
                    rec2.status = "COMPLETED"
                    rec2.total_samples = 1
                    rec2.current_index = 1
                    db2.commit()
            return None

    return FakeBench


def _run_queue(models, behaviors, unload_fail=False):
    """Run the queue loop synchronously with all I/O mocked. Returns (qid, client, calls)."""
    from backend.operations import _run_model_queue_in_thread

    client = _FakeClient(unload_fail=unload_fail)
    calls = []
    fake_bench_cls = _make_fake_bench(behaviors, calls)
    qid = str(uuid.uuid4())

    def _fake_instantiate(bn, db, client_arg, quick_test=False, **kwargs):
        return fake_bench_cls(db, client_arg, quick_test)

    with patch("backend.ops.modelqueue._make_client", return_value=client), \
         patch("backend.ops.modelqueue._instantiate_benchmark", side_effect=_fake_instantiate), \
         patch("backend.ops.modelqueue.time.sleep", return_value=None):
        _run_model_queue_in_thread(qid, models, API_URL, "", 0.0, 2048, "", True)
    return qid, client, calls


def _run_statuses(qid):
    from backend.database import Run, get_db

    with get_db() as db:
        rows = db.query(Run).filter(Run.batch_id == qid).all()
        return {r.model_name: r.status for r in rows}


class TestModelQueueLoop:
    def test_skip_flag_mid_queue_advances_to_next_model(self):
        from backend.operations import (
            _model_queue_lock,
            _model_queue_state,
            get_model_queue_state,
        )

        models = [("m-skip-1", ["MMLU-Pro"]), ("m-skip-2", ["MMLU-Pro"])]
        qid, client, calls = _run_queue(models, {"m-skip-1": "skip"})
        assert client.loaded == ["m-skip-1", "m-skip-2"]
        assert calls == ["m-skip-1", "m-skip-2"]
        assert _run_statuses(qid) == {"m-skip-1": "COMPLETED", "m-skip-2": "COMPLETED"}
        assert get_model_queue_state()["status"] == "completed"
        with _model_queue_lock:
            assert _model_queue_state["skip_model"] is False

    def test_per_model_benchmark_failure_continues_to_next_model(self):
        from backend.operations import get_model_queue_state

        models = [("m-fail-1", ["MMLU-Pro"]), ("m-fail-2", ["MMLU-Pro"])]
        qid, client, calls = _run_queue(models, {"m-fail-1": "fail"})
        # Failed model still unloaded, queue advanced instead of aborting.
        assert client.loaded == ["m-fail-1", "m-fail-2"]
        assert calls == ["m-fail-1", "m-fail-2"]
        assert _run_statuses(qid) == {"m-fail-1": "FAILED", "m-fail-2": "COMPLETED"}
        assert get_model_queue_state()["status"] == "completed"

    def test_unload_failure_handled_without_crash(self):
        from backend.operations import get_model_queue_state

        models = [("m-unload-1", ["MMLU-Pro"]), ("m-unload-2", ["MMLU-Pro"])]
        qid, client, calls = _run_queue(models, {}, unload_fail=True)
        assert client.loaded == ["m-unload-1", "m-unload-2"]
        # Unload attempted for both models despite the exceptions.
        assert client.unloaded == ["m-unload-1", "m-unload-2"]
        assert calls == ["m-unload-1", "m-unload-2"]
        assert _run_statuses(qid) == {"m-unload-1": "COMPLETED", "m-unload-2": "COMPLETED"}
        assert get_model_queue_state()["status"] == "completed"

    def test_halt_mid_run_halts_runs_and_stops_queue(self):
        from backend.operations import get_model_queue_state

        models = [("m-halt-1", ["MMLU-Pro"]), ("m-halt-2", ["MMLU-Pro"])]
        qid, client, calls = _run_queue(models, {"m-halt-1": "halt"})
        # Second model never loaded; halted run stays HALTED in the DB.
        assert client.loaded == ["m-halt-1"]
        assert calls == ["m-halt-1"]
        assert _run_statuses(qid) == {"m-halt-1": "HALTED"}
        # Halt cleanup unloads the current model then resets the queue to
        # idle so a new queue can start (terminal "halted" is transient).
        assert client.unloaded == ["m-halt-1"]
        assert get_model_queue_state()["status"] == "idle"
