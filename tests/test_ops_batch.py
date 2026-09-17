"""Batch / model-queue / export / card / summary coverage (isolated test DB).

Thread-spawning entry points are tested with _start_benchmark_thread /
threading.Thread mocked — no benchmark threads ever start, no LM Studio needed.
Export helpers write timestamped files under records/; tests delete them after.
"""
import os
from unittest.mock import MagicMock, patch

import pytest


def _seed_run(status="COMPLETED", benchmark="MMLU-Pro", model="m",
              total=2, index=2, batch=None, results=0, correct=True):
    from backend.database import Run, Result, get_db
    with get_db() as db:
        run = Run(model_name=model, benchmark_name=benchmark, status=status,
                  current_index=index, total_samples=total,
                  batch_id=batch, parameters='{"quick_test": true}')
        db.add(run)
        db.commit()
        db.refresh(run)
        rid = run.id
        for i in range(results):
            db.add(Result(run_id=rid, task_id=f"t/{i}", prompt="q",
                          raw_response="B", correct=correct,
                          elapsed_time=1.0, tps=10.0, ttft=0.2,
                          thinking_tokens=4, response_tokens=6, prompt_tokens=10))
        db.commit()
        return rid


def _cleanup(path):
    if path and os.path.exists(path):
        os.remove(path)


class TestStartBatch:
    def test_empty_guard(self):
        from backend.operations import start_batch
        rid, bid, msg, df, disp = start_batch("m", [], "http://127.0.0.1:1234/v1")
        assert rid is None and bid == "" and "No benchmarks" in msg

    def test_creates_shared_batch_without_threads(self):
        from backend.operations import start_batch
        from backend.database import Run, get_db
        with patch("backend.ops.lifecycle._start_benchmark_thread",
                   return_value=MagicMock()) as starter:
            first, bid, msg, _df, disp = start_batch(
                "m", ["MMLU-Pro", "TruthfulQA"], "http://127.0.0.1:1234/v1",
                quick_test=True)
            assert starter.called
        assert first is not None and len(bid) == 36 and disp == bid[:8]
        assert "2 benchmarks" in msg
        with get_db() as db:
            runs = db.query(Run).filter(Run.batch_id == bid).all()
            assert len(runs) == 2
            assert {r.benchmark_name for r in runs} == {"MMLU-Pro", "TruthfulQA"}
            assert all(r.status == "PENDING" for r in runs)


class TestModelQueue:
    def test_empty_guard(self):
        from backend.operations import start_model_queue
        qid, msg = start_model_queue([], "http://127.0.0.1:1234/v1")
        assert qid == "" and "No models" in msg

    def test_start_captures_thread_without_running(self):
        from backend.operations import start_model_queue
        captured = {}

        class FakeThread:
            def __init__(self, target=None, args=None, daemon=None):
                captured["target"] = target
                captured["args"] = args

            def start(self):
                captured["started"] = True

        with patch("backend.ops.lifecycle.threading.Thread", FakeThread):
            qid, msg = start_model_queue(
                [("m", ["MMLU-Pro"])], "http://127.0.0.1:1234/v1", quick_test=True)
        assert len(qid) == 36 and "1 model(s), 1 benchmark(s)" in msg
        assert captured.get("started") is True
        assert captured["args"][0] == qid

    def test_halt_idle(self):
        from backend.operations import halt_model_queue
        assert halt_model_queue() == "No active model queue."

    def test_halt_running_halts_batch_runs(self):
        import backend.operations as ops
        from backend.database import Run, get_db
        qid = "test-queue-id"
        r1 = _seed_run(status="RUNNING", batch=qid)
        r2 = _seed_run(status="PENDING", batch=qid)
        with ops._model_queue_lock:
            saved = dict(ops._model_queue_state)
            ops._model_queue_state.update(
                {"status": "running", "queue_id": qid, "message": ""})
        try:
            msg = ops.halt_model_queue()
            assert "halted" in msg.lower()
        finally:
            with ops._model_queue_lock:
                ops._model_queue_state.clear()
                ops._model_queue_state.update(saved)
        with get_db() as db:
            statuses = {r.status for r in
                        db.query(Run).filter(Run.id.in_([r1, r2])).all()}
            assert statuses == {"HALTED"}

    def test_skip_idle(self):
        from backend.operations import skip_current_model
        assert skip_current_model() == "No active model queue."

    def test_skip_running(self):
        import backend.operations as ops
        from backend.database import Run, get_db
        qid = "test-skip-queue"
        rid = _seed_run(status="RUNNING", batch=qid)
        with ops._model_queue_lock:
            saved = dict(ops._model_queue_state)
            ops._model_queue_state.update(
                {"status": "running", "queue_id": qid, "message": ""})
        try:
            assert "Skipping" in ops.skip_current_model()
        finally:
            with ops._model_queue_lock:
                ops._model_queue_state.clear()
                ops._model_queue_state.update(saved)
        with get_db() as db:
            assert db.query(Run).filter(Run.id == rid).first().status == "HALTED"

    def test_state_idle_shape(self):
        from backend.operations import get_model_queue_state
        state = get_model_queue_state()
        for key in ("queue_id", "models", "current_model_index", "total_models",
                    "current_benchmark", "status", "message"):
            assert key in state, key


class TestExports:
    def test_export_results_happy(self):
        from backend.operations import export_results
        rid = _seed_run(results=2)
        path, msg = export_results(str(rid), "CSV")
        try:
            assert path is not None and "Exported to" in msg
            with open(path, encoding="utf-8") as f:
                assert "t/0" in f.read()
        finally:
            _cleanup(path)

    def test_export_results_unknown(self):
        from backend.operations import export_results
        path, msg = export_results("999999999", "CSV")
        assert path is None and "not found" in msg.lower()

    def test_export_results_no_results(self):
        from backend.operations import export_results
        rid = _seed_run(results=0)
        path, msg = export_results(str(rid), "CSV")
        assert path is None and "No results" in msg

    def test_export_batch_unknown(self):
        from backend.operations import export_batch_results
        path, msg = export_batch_results("no-such-batch", "CSV")
        assert path is None and "not found" in msg.lower()

    def test_export_batch_happy(self):
        from backend.operations import export_batch_results
        bid = "batch-export-1"
        _seed_run(batch=bid, results=1)
        path, msg = export_batch_results(bid, "CSV")
        try:
            assert path is not None and "Exported to" in msg
        finally:
            _cleanup(path)

    def test_export_all_history(self):
        from backend.operations import export_all_history
        _seed_run()
        path, msg = export_all_history("CSV")
        try:
            assert path is not None and "Exported to" in msg
        finally:
            _cleanup(path)

    def test_export_run_markdown(self):
        from backend.operations import export_run_markdown
        rid = _seed_run(results=1)
        path, msg = export_run_markdown(str(rid))
        try:
            assert path is not None
            with open(path, encoding="utf-8") as f:
                assert "MMLU-Pro" in f.read()
        finally:
            _cleanup(path)

    def test_export_run_markdown_unknown(self):
        from backend.operations import export_run_markdown
        path, msg = export_run_markdown("999999999")
        assert path is None and "not found" in msg.lower()

    def test_export_results_has_run_columns(self):
        from backend.operations import export_results
        rid = _seed_run(results=2)
        path, msg = export_results(str(rid), "CSV")
        try:
            assert path is not None
            with open(path, encoding="utf-8") as f:
                header = f.readline()
            for col in ("model", "benchmark", "run_status", "temperature",
                        "max_tokens", "system_prompt", "quick_test",
                        "api_url", "batch_id", "prompt", "raw_response"):
                assert col in header, col
        finally:
            _cleanup(path)

    def test_export_all_history_has_params(self):
        from backend.operations import export_all_history
        _seed_run()
        path, msg = export_all_history("CSV")
        try:
            assert path is not None
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for col in ("Temperature", "Max Tokens", "System Prompt",
                        "Thinking Tokens", "Response Tokens", "API URL"):
                assert col in content, col
        finally:
            _cleanup(path)

    def test_export_run_markdown_full_detail(self):
        from backend.operations import export_run_markdown
        rid = _seed_run(results=1, correct=False)
        path, msg = export_run_markdown(str(rid))
        try:
            assert path is not None
            with open(path, encoding="utf-8") as f:
                content = f.read()
            assert "## Configuration" in content
            assert "## All Samples" in content
            assert "## Failed Samples" in content
            assert "```\nq\n```" in content
            assert "```\nB\n```" in content
        finally:
            _cleanup(path)


class TestSummaries:
    def test_batch_summary_happy(self):
        from backend.operations import load_batch_summary
        bid = "batch-summary-1"
        _seed_run(batch=bid, results=2)
        summary, chart, latency = load_batch_summary(bid)
        assert not summary.empty
        assert "MMLU-Pro" in summary.to_string()

    def test_batch_summary_unknown(self):
        from backend.operations import load_batch_summary
        summary, _chart, _lat = load_batch_summary("no-such-batch")
        assert summary.empty

    def test_cross_comparison(self):
        from backend.operations import load_cross_comparison
        r1 = _seed_run(model="m1", results=2)
        r2 = _seed_run(model="m2", results=2)
        acc, lat, tok = load_cross_comparison(f"{r1},{r2}")
        assert not acc.empty


class TestTrustedCard:
    def test_unknown_raises(self):
        from backend.operations import build_trusted_card
        with pytest.raises(ValueError, match="not found"):
            build_trusted_card(999999999)

    def test_offline_fallback_no_crash(self):
        """LM Studio unreachable → card still builds with '?' specs.

        Regression: v0 was unbound when the lookup raised, crashing with
        NameError instead of falling back.
        """
        from backend.operations import build_trusted_card
        rid = _seed_run(status="COMPLETED", results=2)
        fake_metrics = {"gpu_name": "Test GPU", "vram_total_mb": 8192,
                        "ram_total_gb": 32.0}

        def _offline(coro):
            coro.close()  # avoid never-awaited coroutine warning
            raise RuntimeError("offline")

        with patch("backend.ops.exports._run_async", side_effect=_offline), \
             patch("backend.ops.exports.get_system_metrics", return_value=fake_metrics):
            card = build_trusted_card(rid)
        assert card["run_id"] == rid
        assert card["correct"] == 2 and card["total"] == 2
        assert card["quant"] == "?"
        assert "[quick-test]" in card["text"]
        assert "(2/2," in card["text"]
        assert "Test GPU" in card["hardware"]
