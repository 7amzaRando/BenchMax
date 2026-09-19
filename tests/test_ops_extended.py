"""Extended operations + run-loop tests (isolated test DB via conftest).

Covers: pause/halt/resume transitions, delete_runs, export_selected_runs,
generate_diff fallbacks, BaseBenchmark loop (exception continuation,
None-response guard, empty dataset), multi-turn user-first guard,
scoring None-inputs, client-exception sample behavior.
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


def _seed_run(status="RUNNING", benchmark="MMLU-Pro", model="m", total=5, index=0):
    from backend.database import Run, get_db
    with get_db() as db:
        run = Run(model_name=model, benchmark_name=benchmark, status=status,
                  current_index=index, total_samples=total,
                  parameters='{"quick_test": true}')
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id


class TestPauseHalt:
    def test_pause_not_found(self):
        from backend.operations import pause_run
        assert pause_run(999999999) == "Run not found."

    def test_pause_wrong_status(self):
        from backend.operations import pause_run
        rid = _seed_run(status="COMPLETED")
        assert "Cannot pause" in pause_run(rid)

    def test_pause_happy_path(self):
        from backend.operations import pause_run
        from backend.database import Run, get_db
        rid = _seed_run(status="RUNNING")
        assert "paused" in pause_run(rid).lower()
        with get_db() as db:
            assert db.query(Run).filter(Run.id == rid).first().status == "PAUSED"

    def test_halt_not_found(self):
        from backend.operations import halt_run
        assert halt_run(999999999) == "Run not found."

    def test_halt_happy_path(self):
        from backend.operations import halt_run
        from backend.database import Run, get_db
        rid = _seed_run(status="RUNNING")
        halt_run(rid)
        with get_db() as db:
            assert db.query(Run).filter(Run.id == rid).first().status == "HALTED"


class TestResumeGuards:
    def test_not_found(self):
        from backend.operations import resume_run
        assert resume_run(999999999) == "Run not found."

    def test_completed_refused(self):
        from backend.operations import resume_run
        rid = _seed_run(status="COMPLETED")
        assert "already COMPLETED" in resume_run(rid)

    def test_running_refused(self):
        from backend.operations import resume_run
        rid = _seed_run(status="RUNNING")
        assert "currently RUNNING" in resume_run(rid)

    def test_paused_resumes_with_mocked_thread(self):
        from backend.operations import resume_run
        from backend.database import Run, get_db
        rid = _seed_run(status="PAUSED", benchmark="MMLU-Pro")
        with patch("backend.ops.lifecycle._start_benchmark_thread", return_value=MagicMock()) as starter:
            msg = resume_run(rid)
            assert "resumed" in msg.lower()
            assert starter.called
        with get_db() as db:
            assert db.query(Run).filter(Run.id == rid).first().status == "RUNNING"


class TestDeleteExport:
    def test_delete_invalid_ids(self):
        from backend.operations import delete_runs
        _, msg = delete_runs("abc,!!")
        assert msg == "No valid run IDs provided."

    def test_delete_happy_path(self):
        from backend.operations import delete_runs
        from backend.database import Run, get_db
        rid = _seed_run(status="COMPLETED")
        _, msg = delete_runs(str(rid))
        assert str(rid) in msg
        with get_db() as db:
            assert db.query(Run).filter(Run.id == rid).first() is None

    def test_export_selected_csv(self):
        import os
        from backend.operations import export_selected_runs
        rid = _seed_run(status="COMPLETED")
        content, msg = export_selected_runs(str(rid), format_type="CSV")
        assert content is not None
        assert "exported to" in msg.lower()
        try:
            with open(content, encoding="utf-8") as f:
                body = f.read()
            assert str(rid) in body
        finally:
            if content and os.path.exists(content):
                os.remove(content)

    def test_export_empty_guard(self):
        from backend.operations import export_selected_runs
        content, _ = export_selected_runs("", format_type="CSV")
        assert content is None


class TestGenerateDiff:
    def test_unknown_run(self):
        from backend.operations import generate_diff
        assert "not found" in generate_diff("999999999", "t/0").lower()

    def test_removed_benchmark_fallback(self):
        from backend.operations import generate_diff
        from backend.database import Run, Result, get_db
        with get_db() as db:
            run = Run(model_name="m", benchmark_name="MCP-Bench", status="COMPLETED",
                      current_index=1, total_samples=1)
            db.add(run)
            db.commit()
            db.refresh(run)
            rid = run.id
            db.add(Result(run_id=rid, task_id="mcp/0", prompt="Do X",
                          raw_response="did Y", extracted_code="code Y", correct=False))
            db.commit()
        html = generate_diff(str(rid), "mcp/0")
        assert "no longer available" in html
        assert "Do X" in html


class TestBaseLoop:
    def _fake_bench(self, behaviors):
        """behaviors: list of 'ok' | 'raise' | 'none' per sample."""
        from backend.benchmarks.base import BaseBenchmark

        class FakeBench(BaseBenchmark):
            def load_dataset(self):
                return [{"task_id": f"t/{i}"} for i in range(len(behaviors))]

            async def evaluate_sample(self, sample, params, model_name):
                mode = behaviors[int(sample["task_id"].split("/")[1])]
                if mode == "raise":
                    raise RuntimeError("boom")
                if mode == "none":
                    return None
                return self._result("p", {"raw_response": "r", "answer_content": "r",
                                          "elapsed_time": 0.1, "tps": 1.0, "ttft": 0.1,
                                          "thinking_tokens": 0, "response_tokens": 1,
                                          "prompt_tokens": 1},
                                    correct=True)
        return FakeBench

    def test_exception_continues_and_writes_failed(self):
        import backend.database as dbmod
        from backend.database import Run, Result, get_db
        FakeBench = self._fake_bench(["ok", "raise", "ok"])
        with get_db() as db:
            run = Run(model_name="m", benchmark_name="Fake", status="RUNNING",
                      current_index=0, total_samples=3, parameters="{}")
            db.add(run)
            db.commit()
            db.refresh(run)
            rid = run.id
        sess = dbmod.SessionLocal()
        try:
            bench = FakeBench(sess, MagicMock())
            asyncio.run(bench.run_evaluation(rid, {}))
        finally:
            sess.close()
        with get_db() as db:
            rows = db.query(Result).filter(Result.run_id == rid).order_by(Result.id).all()
            assert len(rows) == 3
            assert rows[0].correct is True
            assert rows[1].correct is False
            assert "boom" in (rows[1].error_message or "")
            assert rows[2].correct is True
            assert db.query(Run).filter(Run.id == rid).first().status == "COMPLETED"

    def test_empty_dataset_marks_failed(self):
        import backend.database as dbmod
        from backend.database import Run, get_db
        from backend.benchmarks.base import BaseBenchmark

        class EmptyBench(BaseBenchmark):
            def load_dataset(self):
                return []

            async def evaluate_sample(self, sample, params, model_name):
                raise AssertionError("should not be called")

        with get_db() as db:
            run = Run(model_name="m", benchmark_name="Fake", status="RUNNING",
                      current_index=0, total_samples=0, parameters="{}")
            db.add(run)
            db.commit()
            db.refresh(run)
            rid = run.id
        sess = dbmod.SessionLocal()
        try:
            asyncio.run(EmptyBench(sess, MagicMock()).run_evaluation(rid, {}))
        finally:
            sess.close()
        with get_db() as db:
            assert db.query(Run).filter(Run.id == rid).first().status == "FAILED"


class TestScoringNone:
    @pytest.mark.parametrize("fn", ["score_mcq", "score_mcq_multi", "score_code",
                                    "score_exact", "score_exact_multi", "score_free_form"])
    def test_none_response_is_false_not_crash(self, fn):
        import backend.benchmarks.scoring as scoring
        ok, err = getattr(scoring, fn)(None, "A")
        assert ok is False
        assert isinstance(err, str) and err


class TestClientExceptionSample:
    def test_aime_propagates_client_error_to_loop(self):
        """Sample-level raise is the contract; the base loop converts it to
        a failed Result (covered in TestBaseLoop). Pin so silent-swallowing
        regressions are caught."""
        from backend.benchmarks.aime import AIMEBenchmark
        db = MagicMock()
        client = MagicMock()
        client.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
        bench = AIMEBenchmark(db, client, quick_test=True)
        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(bench.evaluate_sample(
                {"task_id": "a/0", "problem": "q", "answer": "42"}, {}, "m"))


class TestExportBranches:
    def test_export_dataframe_json_branch(self):
        import os
        import pandas as pd
        from backend.ops.exports import _export_dataframe
        df = pd.DataFrame([{"a": 1, "b": "x"}])
        path, msg = _export_dataframe(df, "probe", "JSON")
        try:
            assert path is not None and path.endswith(".json")
            assert os.path.getsize(path) > 0
        finally:
            if path and os.path.exists(path):
                os.remove(path)

    def test_export_dataframe_xlsx_branch(self):
        import os
        import pandas as pd
        from backend.ops.exports import _export_dataframe
        df = pd.DataFrame([{"a": 1, "b": "x"}])
        path, msg = _export_dataframe(df, "probe", "XLSX")
        try:
            assert path is not None and path.endswith(".xlsx")
            assert os.path.getsize(path) > 0
        finally:
            if path and os.path.exists(path):
                os.remove(path)

    def test_export_file_or_404_empty_raises_404(self):
        from fastapi import HTTPException
        from backend.api import _export_file_or_404
        with pytest.raises(HTTPException) as exc:
            _export_file_or_404(None, "No results to export.", "CSV")
        assert exc.value.status_code == 404

    def test_run_markdown_has_configuration_and_samples(self):
        import os
        from backend.operations import export_run_markdown
        from backend.database import Result, get_db
        rid = _seed_run(status="COMPLETED")
        with get_db() as db:
            db.add(Result(run_id=rid, task_id="t/0", prompt="q",
                          raw_response="B", correct=True,
                          elapsed_time=1.0, tps=10.0, ttft=0.2,
                          thinking_tokens=4, response_tokens=6, prompt_tokens=10))
            db.commit()
        path, _ = export_run_markdown(str(rid))
        try:
            assert path is not None
            with open(path, encoding="utf-8") as f:
                content = f.read()
            assert "## Configuration" in content
            assert "## All Samples" in content
        finally:
            if path and os.path.exists(path):
                os.remove(path)


class TestDatasetInstallPaths:
    def test_install_unknown_dataset_errors_without_network(self):
        """Unknown benchmark name errors out before any subprocess/network call."""
        from backend.ops import datasets as dsmod
        with patch.object(dsmod.subprocess, "run",
                          side_effect=AssertionError("must not hit subprocess")):
            msg = asyncio.run(dsmod.install_dataset("NoSuchBench"))
        assert "No dataset entry" in msg

    def test_hf_token_roundtrip(self, tmp_path):
        from backend.ops import datasets as dsmod
        fake = tmp_path / ".hf_token"
        with patch.object(dsmod, "HF_TOKEN_FILE", fake):
            assert dsmod._save_hf_token("tok123") == "Token saved."
            assert dsmod._load_hf_token() == "tok123"
