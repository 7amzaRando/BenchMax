"""Tests for run lifecycle operations (trigger, pause, halt, resume)."""
import json
import threading
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestCheckBenchmarkReadiness:
    def test_ready_benchmark(self):
        from backend.operations import check_benchmark_readiness
        issues = check_benchmark_readiness("HumanEval", quick_test=True)
        assert isinstance(issues, list)
        # Quick test skips dataset check, so should be empty or runtime-only
        for issue in issues:
            assert "kind" in issue
            assert "action" in issue

    def test_unknown_benchmark(self):
        from backend.operations import check_benchmark_readiness
        issues = check_benchmark_readiness("Nonexistent Benchmark")
        assert isinstance(issues, list)


class TestInstantiateBenchmark:
    def test_known_benchmarks(self):
        from backend.operations import _instantiate_benchmark
        db = MagicMock()
        client = MagicMock()
        for name in ["HumanEval", "MMLU-Pro", "TruthfulQA"]:
            bench = _instantiate_benchmark(name, db, client, quick_test=True)
            assert bench is not None

    def test_unknown_raises(self):
        from backend.operations import _instantiate_benchmark
        db = MagicMock()
        client = MagicMock()
        with pytest.raises(ValueError, match="Unknown benchmark"):
            _instantiate_benchmark("FakeBenchmark", db, client)


class TestBuildRunParams:
    def test_basic_params(self):
        from backend.operations import _build_run_params
        params = _build_run_params(
            api_url="http://127.0.0.1:1234/v1",
            max_tokens=4096,
            sys_prompt="You are helpful.",
            temp=0.7,
            quick_test=True,
            disable_rep_detection=False,
        )
        assert params["api_url"] == "http://127.0.0.1:1234/v1"
        assert params["max_completion_tokens"] == 4096
        assert params["system_prompt"] == "You are helpful."
        assert params["temperature"] == 0.7
        assert params["quick_test"] is True

    def test_none_temp(self):
        from backend.operations import _build_run_params
        params = _build_run_params(
            api_url="http://127.0.0.1:1234/v1",
            max_tokens=2048,
            sys_prompt="",
            temp=None,
            quick_test=False,
            disable_rep_detection=False,
        )
        assert "temperature" not in params


class TestPollStructure:
    def test_poll_returns_expected_keys(self):
        from backend.operations import poll
        result = poll(active_run_id=None)
        assert isinstance(result, dict)
        # Should have telemetry keys
        assert "cpu_text" in result or "metrics" in result


class TestLiveProgress:
    def test_counter_roundtrip(self):
        from backend.benchmarks.base import (
            set_live_progress, get_live_progress, clear_live_progress)
        assert get_live_progress(999999) is None
        set_live_progress(999999, 7)
        assert get_live_progress(999999) == 7
        clear_live_progress(999999)
        assert get_live_progress(999999) is None

    def test_run_progress_prefers_live_counter(self):
        from backend.benchmarks.base import set_live_progress, clear_live_progress
        from backend.operations import _compute_run_progress
        run = MagicMock()
        run.id = 999998
        run.benchmark_name = "HumanEval"
        run.status = "RUNNING"
        run.total_samples = 100
        run.current_index = 5  # last committed flush
        stats = {"avg_tps": 10.0, "avg_ttft": 0.5, "avg_prompt_tps": 20.0,
                 "accuracy": "50.0%", "think_tk": 10, "resp_tk": 10, "total_tk": 20}
        try:
            set_live_progress(999998, 9)  # 4 more samples done since flush
            rp = _compute_run_progress(run, stats=stats)
            assert rp["prog_val"] == 0.09
            assert "(9/100)" in rp["status_md"]
        finally:
            clear_live_progress(999998)
        rp = _compute_run_progress(run, stats=stats)
        assert rp["prog_val"] == 0.05
        assert "(5/100)" in rp["status_md"]
