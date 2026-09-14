"""Tests for backend/benchmarks/multi_turn_base.py — pure helpers + scripted loop.

No LLM calls: a scripted FakeMultiTurn subclass drives evaluate_sample with
_get_model_context_limit mocked. No network, no Docker.
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock


class FakeMultiTurn:
    """Factory for scripted MultiTurnBenchmark subclasses."""
    @staticmethod
    def make(script, score_result=None, tools_impl=None):
        from backend.benchmarks.multi_turn_base import MultiTurnBenchmark

        class _Fake(MultiTurnBenchmark):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.calls = list(script)

            def load_dataset(self):
                return [{"task_id": "mt/0",
                         "turns": [{"role": "user", "content": "do the thing"}],
                         "ground_truth": "42"}]

            async def evaluate_turn(self, turn_idx, conversation, sample, params, model_name):
                if not self.calls:
                    return {"response": "", "tool_calls": None, "done": True}
                return self.calls.pop(0)

            def score(self, sample, conversation, final_response):
                return score_result or {"correct": True, "score": 1.0, "details": {}}

            if tools_impl is not None:
                async def execute_tools(self, tool_calls, sample):
                    return await tools_impl(tool_calls, sample)

        return _Fake


def _gen(t=2, r=3, p=5):
    return {"thinking_tokens": t, "response_tokens": r, "prompt_tokens": p,
            "elapsed_time": 0.5, "tps": 10.0, "ttft": 0.1}


class TestLiveTurnHelpers:
    def test_set_get_clear(self):
        from backend.benchmarks.multi_turn_base import (
            get_live_turn_state, _set_live_turn, _clear_live_turn)
        _clear_live_turn()
        assert get_live_turn_state() == {}
        _set_live_turn(7, 2, 5, 1.5)
        state = get_live_turn_state()
        assert state["run_id"] == 7 and state["turn"] == 2 and state["max_turns"] == 5
        _clear_live_turn()
        assert get_live_turn_state() == {}

    def test_snapshot_is_copy(self):
        from backend.benchmarks.multi_turn_base import (
            get_live_turn_state, _set_live_turn, _clear_live_turn)
        _set_live_turn(1, 1, 3, 0.1)
        get_live_turn_state()["turn"] = 999
        assert get_live_turn_state()["turn"] == 1
        _clear_live_turn()


class TestExecuteToolsDefault:
    def test_unknown_tool_error(self):
        bench = FakeMultiTurn.make([])(MagicMock(), MagicMock())
        out = asyncio.run(bench.execute_tools([{"name": "nope"}], {}))
        assert out[0]["role"] == "tool"
        assert "nope" in out[0]["content"]


class TestTruncate:
    def _bench(self):
        return FakeMultiTurn.make([])(MagicMock(), MagicMock())

    def test_under_budget_untouched(self):
        b = self._bench()
        conv = [{"role": "user", "content": "hi"}]
        assert b._truncate_conversation(conv, 1000) == [{"role": "user", "content": "hi"}]

    def test_preserves_system_drops_oldest(self):
        b = self._bench()
        big = "x" * 4000  # ~1000 tokens each
        conv = [{"role": "system", "content": "sys"},
                {"role": "user", "content": big},
                {"role": "assistant", "content": big},
                {"role": "user", "content": big},
                {"role": "assistant", "content": "fresh"}]
        out = b._truncate_conversation(conv, 1500)
        assert out[0]["role"] == "system"
        assert out[-1]["content"] == "fresh"
        assert sum(len(m["content"]) for m in out) // 4 <= 1500

    def test_ensure_user_first_strips_greeting(self):
        from backend.benchmarks.multi_turn_base import MultiTurnBenchmark
        conv = [{"role": "assistant", "content": "hello!"},
                {"role": "user", "content": "q"}]
        out = MultiTurnBenchmark._ensure_user_first(conv)
        assert out[0]["role"] == "user"

    def test_ensure_user_first_keeps_system(self):
        from backend.benchmarks.multi_turn_base import MultiTurnBenchmark
        conv = [{"role": "system", "content": "s"},
                {"role": "assistant", "content": "hi"},
                {"role": "user", "content": "q"}]
        out = MultiTurnBenchmark._ensure_user_first(conv)
        assert out[0]["role"] == "system" and out[1]["role"] == "user"

    def test_ensure_user_first_empty(self):
        from backend.benchmarks.multi_turn_base import MultiTurnBenchmark
        assert MultiTurnBenchmark._ensure_user_first([]) == []


class TestContextLimit:
    def test_fallback_on_error(self):
        from backend.benchmarks.multi_turn_base import _DEFAULT_MAX_CONTEXT_TOKENS
        bench = FakeMultiTurn.make([])(MagicMock(), MagicMock())
        bench.client = MagicMock()
        bench.client.base_url = "http://127.0.0.1:1234/v1"
        fake_http = MagicMock()
        fake_http.get = AsyncMock(side_effect=RuntimeError("offline"))
        bench.client._get_client = MagicMock(return_value=fake_http)
        assert asyncio.run(bench._get_model_context_limit("m")) == _DEFAULT_MAX_CONTEXT_TOKENS

    def test_loaded_context_preferred(self):
        bench = FakeMultiTurn.make([])(MagicMock(), MagicMock())
        bench.client = MagicMock()
        bench.client.base_url = "http://127.0.0.1:1234/v1"
        resp = MagicMock()
        resp.status_code = 200
        resp.json = MagicMock(return_value={
            "data": [{"key": "m", "max_context_length": 99999,
                      "loaded_instances": [{"config": {"context_length": 12345}}]}]})
        fake_http = MagicMock()
        fake_http.get = AsyncMock(return_value=resp)
        bench.client._get_client = MagicMock(return_value=fake_http)
        assert asyncio.run(bench._get_model_context_limit("m")) == 12345


class TestEvaluateSampleLoop:
    def _run(self, bench, sample_extra=None):
        bench._get_model_context_limit = AsyncMock(return_value=32768)
        sample = {"task_id": "mt/0",
                  "turns": [{"role": "user", "content": "do the thing"}],
                  "ground_truth": "42", "max_turns": 5}
        if sample_extra:
            sample.update(sample_extra)
        return asyncio.run(bench.evaluate_sample(sample, {}, "m"))

    def test_done_first_turn_scores(self):
        bench = FakeMultiTurn.make(
            [{"response": "42", "tool_calls": None, "done": True, "gen": _gen()}]
        )(MagicMock(), MagicMock())
        out = self._run(bench)
        assert out["correct"] is True
        assert out["tps"] == 10.0
        assert out["response_tokens"] == 3
        details = out.get("scoring_details") or {}
        import json
        sd = details if isinstance(details, dict) else json.loads(details)
        assert sd["turns_used"] == 1

    def test_tools_execute_before_done(self):
        async def _tools(calls, sample):
            return [{"role": "tool", "content": "calc=42"}]

        bench = FakeMultiTurn.make(
            [{"response": "calling", "tool_calls": [{"name": "calc"}],
              "done": True, "gen": _gen()}],
            score_result={"correct": True, "score": 1.0, "details": {}},
            tools_impl=_tools,
        )(MagicMock(), MagicMock())
        out = self._run(bench)
        assert out["correct"] is True
        import json
        sd = out["scoring_details"] if isinstance(out["scoring_details"], dict) \
            else json.loads(out["scoring_details"])
        roles = [t["role"] for t in sd["turns"]]
        assert "tool" in roles

    def test_empty_response_stops(self):
        bench = FakeMultiTurn.make(
            [{"response": "   ", "tool_calls": None, "done": False}]
        )(MagicMock(), MagicMock())
        out = self._run(bench)
        assert out["correct"] is True  # scripted score passes; loop stopped, not hung

    def test_turn_error_fails_sample(self):
        class _Boom(FakeMultiTurn.make([])):
            async def evaluate_turn(self, *a, **k):
                raise RuntimeError("turn boom")

        out = self._run(_Boom(MagicMock(), MagicMock()))
        assert out["correct"] is False
        assert "turn boom" in (out["error_message"] or "")

    def test_score_error_fails_sample(self):
        bench = FakeMultiTurn.make(
            [{"response": "x", "tool_calls": None, "done": True, "gen": _gen()}],
            score_result=None,
        )(MagicMock(), MagicMock())

        def _bad_score(sample, conv, final):
            raise RuntimeError("score boom")

        bench.score = _bad_score
        out = self._run(bench)
        assert out["correct"] is False
        assert "score boom" in (out["error_message"] or "").lower()

    def test_wall_clock_cap(self):
        bench = FakeMultiTurn.make(
            [{"response": "x", "tool_calls": None, "done": False, "gen": _gen()}],
            score_result={"correct": False, "score": 0.0,
                          "details": {"error": "timed out"}},
        )(MagicMock(), MagicMock())
        out = self._run(bench, {"max_wall_clock_sec": 0})
        assert out["correct"] is False
        assert "TIMEOUT" in (out["raw_response"] or "")
