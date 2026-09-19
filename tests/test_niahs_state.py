"""Tests for NIAHS haystack logic and ops/state helpers.

NIAHS evaluate_sample is fully hermetic: _load_corpus and _generate are
mocked, needles are pinned deterministic. No LLM, no disk corpus needed.
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


def _niahs_bench():
    from backend.benchmarks.niahs import NIAHSBenchmark
    bench = NIAHSBenchmark(MagicMock(), MagicMock(), quick_test=True)
    bench._load_corpus = MagicMock(return_value="lorem ipsum dolor sit amet " * 200)
    return bench


def _gen_with(answer):
    return {"raw_response": answer, "answer_content": answer,
            "elapsed_time": 0.5, "tps": 10.0, "ttft": 0.1,
            "thinking_tokens": 0, "response_tokens": 5, "prompt_tokens": 50}


class TestNeedles:
    def test_format_8_digits(self):
        from backend.benchmarks.niahs import _random_needle
        for _ in range(20):
            v = _random_needle()
            assert len(v) == 8 and v.isdigit()

    def test_dataset_shape(self):
        bench = _niahs_bench()
        ds = bench.load_dataset()
        assert len(ds) == 3
        assert ds[0]["task_id"] == "niahs_run0"
        assert ds[0]["depths"] == [0.10, 0.25, 0.50, 0.75, 0.90]


class TestHaystack:
    def test_scales_with_context(self):
        bench = _niahs_bench()
        small = bench._generate_haystack(100)
        big = bench._generate_haystack(10000)
        assert len(small) == 100 * 4
        assert len(big) == 10000 * 4

    def test_repeats_short_corpus(self):
        bench = _niahs_bench()
        bench._load_corpus = MagicMock(return_value="abc ")
        out = bench._generate_haystack(1000)
        assert len(out) == 4000
        assert out.startswith("abc ")


class TestEvaluateSample:
    def _run(self, response_fn):
        bench = _niahs_bench()
        needles = ["11111111", "22222222", "33333333", "44444444", "55555555"]
        with patch("backend.benchmarks.niahs._random_needle", side_effect=needles):
            bench._generate = AsyncMock(side_effect=response_fn(needles))
            sample = {"task_id": "niahs_run0",
                      "depths": [0.10, 0.25, 0.50, 0.75, 0.90]}
            return asyncio.run(bench.evaluate_sample(
                sample, {"context_length": 256}, "m"))

    def test_all_found_correct(self):
        def _resp(needles):
            async def _g(prompt, params, model):
                return _gen_with(", ".join(needles))
            return _g
        out = self._run(_resp)
        assert out["correct"] is True
        assert out["error_message"] is None

    def test_strict_missing_one_fails(self):
        def _resp(needles):
            async def _g(prompt, params, model):
                return _gen_with(", ".join(needles[:4]))
            return _g
        out = self._run(_resp)
        assert out["correct"] is False
        assert "Missing" in (out["error_message"] or "")
        assert "55555555" in (out["error_message"] or "")

    def test_empty_response_reports_expected(self):
        async def _g(prompt, params, model):
            return _gen_with("")
        bench = _niahs_bench()
        needles = ["11111111", "22222222", "33333333", "44444444", "55555555"]
        with patch("backend.benchmarks.niahs._random_needle", side_effect=needles):
            bench._generate = AsyncMock(side_effect=_g)
            out = asyncio.run(bench.evaluate_sample(
                {"task_id": "niahs_run0", "depths": [0.10]},
                {"context_length": 256}, "m"))
        assert out["correct"] is False
        assert "11111111" in (out["error_message"] or "")


class TestOpsState:
    def test_constants(self):
        from backend.ops import state
        assert state.MAX_HISTORY_LEN == 300
        assert state._active_batch_id is None
        assert state._model_queue_state["status"] == "idle"

    def test_skip_flag_roundtrip(self):
        from backend.ops.state import (
            _queue_skip_model_requested, _clear_skip_model_flag,
            _model_queue_state, _model_queue_lock)
        with _model_queue_lock:
            saved = _model_queue_state.get("skip_model", False)
            _model_queue_state["skip_model"] = True
        try:
            assert _queue_skip_model_requested() is True
            _clear_skip_model_flag()
            assert _queue_skip_model_requested() is False
        finally:
            with _model_queue_lock:
                _model_queue_state["skip_model"] = saved

    def test_queue_halted(self):
        from backend.ops.state import _queue_halted, _model_queue_state, _model_queue_lock
        with _model_queue_lock:
            saved = _model_queue_state.get("status")
            _model_queue_state["status"] = "halted"
        try:
            assert _queue_halted() is True
        finally:
            with _model_queue_lock:
                _model_queue_state["status"] = saved

    def test_docker_daemon_check_bool(self):
        from backend.ops.state import _docker_daemon_running
        assert isinstance(_docker_daemon_running(), bool)
