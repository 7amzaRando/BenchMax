"""Smoke coverage for ALL 30 registered benchmarks (registration + mini dataset shape).

Fast and hermetic: instantiation + load_dataset only. No LLM calls, no Docker.
Docker-backed evaluate_sample paths are covered by test_safe_executor.py
(INTEGRATION, Docker-gated) and test_benchmarks.py (mocked client).
"""
import inspect

import pytest
from unittest.mock import MagicMock


def _all_names():
    from backend.config import BENCHMARKS
    return [name for _, name in BENCHMARKS]


class TestRegistration:
    def test_at_least_30_registered(self):
        assert len(_all_names()) >= 30

    def test_unknown_raises(self):
        from backend.operations import _instantiate_benchmark
        with pytest.raises(ValueError, match="Unknown benchmark"):
            _instantiate_benchmark("NopeBench", MagicMock(), MagicMock(), quick_test=True)

    @pytest.mark.parametrize("name", _all_names())
    def test_instantiates(self, name):
        from backend.operations import _instantiate_benchmark
        bench = _instantiate_benchmark(name, MagicMock(), MagicMock(), quick_test=True)
        assert bench is not None
        assert inspect.iscoroutinefunction(bench.evaluate_sample)
        assert callable(bench.load_dataset)


class TestMiniDatasets:
    @pytest.mark.parametrize("name", _all_names())
    def test_mini_loads_nonempty_with_ids(self, name):
        from backend.operations import _instantiate_benchmark
        bench = _instantiate_benchmark(name, MagicMock(), MagicMock(), quick_test=True)
        ds = bench.load_dataset()
        assert isinstance(ds, list) and len(ds) > 0
        first = ds[0]
        assert isinstance(first, dict)
        # Every sample must carry some task identifier
        assert any(k in first for k in (
            "task_id", "question_id", "key", "id", "problem_id", "name")), first.keys()
