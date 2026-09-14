"""Regression tests for the all-benchmark scoring sweep.

Pure unit tests — no Docker, no LM Studio required.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _run_async(coro):
    return asyncio.run(coro)


def _mock_gen(response="x"):
    return {
        "model_name": "test-model",
        "raw_response": response,
        "thinking_content": "",
        "answer_content": response,
        "elapsed_time": 1.5,
        "ttft": 0.3,
        "tps": 50.0,
        "prompt_tokens": 100,
        "response_tokens": 20,
        "thinking_tokens": 0,
        "answer_tokens": 20,
        "stream_timed_out": False,
    }


# ── scoring.py fail-closed ─────────────────────────────────────────

class TestScoringFailClosed:
    def test_free_form_empty_answer(self):
        from backend.benchmarks.scoring import score_free_form
        ok, err = score_free_form("any response", "")
        assert ok is False
        assert "ground-truth" in err.lower() or "configured" in err.lower()

    def test_score_code_empty_func(self):
        from backend.benchmarks.scoring import score_code
        ok, _ = score_code("def anything():\n    pass", "")
        assert ok is False

    def test_score_code_fence_mention_without_def(self):
        from backend.benchmarks.scoring import score_code
        ok, _ = score_code("```\ncall encode() here\n```", "encode")
        assert ok is False

    def test_score_sample_unknown_type(self):
        from backend.benchmarks.scoring import score_sample
        ok, err = score_sample("text", {"type": "nonsense_xyz", "answer": "text"})
        assert ok is False
        assert "Unknown" in err

    def test_score_sample_missing_type_legacy(self):
        from backend.benchmarks.scoring import score_sample
        ok, _ = score_sample("I love python", {"answer": "python"})
        assert ok is True

    def test_int_constraint_malformed_spec(self):
        from backend.benchmarks.scoring import _check_int_constraint
        err = _check_int_constraint(5, {"eq": "not-a-number"}, "word_count")
        assert err is not None
        assert "malformed" in err


# ── MCQ anti-hedge routing ─────────────────────────────────────────

class TestMCQRouting:
    def _bench(self, response):
        from backend.benchmarks.mmlu_pro import MMLUProBenchmark
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen(response))
        return MMLUProBenchmark(MagicMock(), client, quick_test=True)

    def test_correct(self):
        bench = self._bench("B")
        sample = {"task_id": "m/0", "question": "q?", "options": ["a", "b", "c", "d"], "answer": "B"}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0, "max_completion_tokens": 10}, "t"))
        assert res["correct"] is True

    def test_hedging_fails(self):
        bench = self._bench("A... actually B")
        sample = {"task_id": "m/0", "question": "q?", "options": ["a", "b", "c", "d"], "answer": "B"}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0, "max_completion_tokens": 10}, "t"))
        assert res["correct"] is False
        assert "edg" in (res["error_message"] or "").lower()

    def test_out_of_range_letter_ignored(self):
        # 4 options shown (A-D); a stray J in prose must not count.
        bench = self._bench("I think J is nice, but the answer is B")
        sample = {"task_id": "m/0", "question": "q?", "options": ["a", "b", "c", "d"], "answer": "B"}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0, "max_completion_tokens": 10}, "t"))
        assert res["correct"] is True

    def test_mmmu_no_options(self):
        from backend.benchmarks.mmmu_pro import MMMUProBenchmark
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen("A"))
        bench = MMMUProBenchmark(MagicMock(), client, quick_test=True)
        sample = {"task_id": "v/0", "question": "q?", "options": [], "answer": "A", "image_paths": []}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0, "max_completion_tokens": 10}, "t"))
        assert res["correct"] is False
        assert "options" in (res["error_message"] or "").lower()


# ── LiveBench list/JSON grading ────────────────────────────────────

class TestLiveBenchLists:
    def _bench(self, response):
        from backend.benchmarks.livebench import LiveBenchBenchmark
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen(response))
        return LiveBenchBenchmark(MagicMock(), client, quick_test=True)

    def test_reasoning_correct(self):
        bench = self._bench("Answer: 1, filmmaking, police-officer, journalist")
        sample = {"task_id": "r/0", "category": "reasoning",
                  "question": "puzzle?", "options": [],
                  "answer": "1, filmmaking, police-officer, journalist"}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        assert res["correct"] is True

    def test_reasoning_wrong_order(self):
        bench = self._bench("Answer: filmmaking, 1, police-officer, journalist")
        sample = {"task_id": "r/0", "category": "reasoning",
                  "question": "puzzle?", "options": [],
                  "answer": "1, filmmaking, police-officer, journalist"}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        assert res["correct"] is False

    def test_reasoning_gibberish_fails(self):
        bench = self._bench("I think it might be C")
        sample = {"task_id": "r/0", "category": "reasoning",
                  "question": "puzzle?", "options": [],
                  "answer": "1, filmmaking, police-officer, journalist"}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        assert res["correct"] is False

    def test_data_analysis_json(self):
        import json
        expected = {"69": {"a": 1}, "88": {"a": 0}}
        bench = self._bench("```json\n" + json.dumps(expected) + "\n```")
        sample = {"task_id": "d/0", "category": "data_analysis",
                  "question": "convert", "options": [], "answer": json.dumps(expected)}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        assert res["correct"] is True

    def test_language_list(self):
        bench = self._bench("Answer: lather, stew, sweat")
        sample = {"task_id": "l/0", "category": "language",
                  "question": "sort?", "options": [], "answer": "lather, stew, sweat"}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        assert res["correct"] is True


# ── BFCL ───────────────────────────────────────────────────────────

class TestBFCL:
    def test_imports_without_language(self):
        import backend.benchmarks.bfcl  # must not raise ImportError
        assert hasattr(backend.benchmarks.bfcl, "BFCLBenchmark")

    def test_single_turn_correct(self):
        from backend.benchmarks.bfcl import BFCLBenchmark
        client = MagicMock()
        body = '[{"name": "get_current_weather", "arguments": {"location": "Tokyo"}}]'
        client.generate_completion = AsyncMock(return_value=_mock_gen(body))
        bench = BFCLBenchmark(MagicMock(), client, quick_test=True)
        sample = {
            "id": "simple_0", "category": "simple",
            "question": "Weather in Tokyo?",
            "function": [{"name": "get_current_weather", "description": "w",
                          "parameters": {"type": "object",
                                         "properties": {"location": {"type": "string"}},
                                         "required": ["location"]}}],
            "answer": [{"name": "get_current_weather", "arguments": {"location": "Tokyo"}}],
        }
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        assert res["correct"] is True
        assert res["scoring_details"]["category"] == "simple"

    def test_irrelevance_abstain(self):
        from backend.benchmarks.bfcl import BFCLBenchmark
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen("[]"))
        bench = BFCLBenchmark(MagicMock(), client, quick_test=True)
        sample = {"id": "irr_0", "category": "irrelevance", "question": "Tell me a joke.",
                  "function": [{"name": "f", "description": "d",
                                "parameters": {"type": "object", "properties": {}, "required": []}}],
                  "answer": []}
        res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        assert res["correct"] is True

    def test_multi_turn_accounting(self):
        from backend.benchmarks.bfcl import BFCLBenchmark
        client = MagicMock()
        body = '[{"name": "cd", "arguments": {"folder": "documents"}}]'
        gen1 = _mock_gen(body)
        gen1.update({"elapsed_time": 2.0, "tps": 10.0, "ttft": 0.5,
                     "response_tokens": 20, "thinking_tokens": 0, "prompt_tokens": 30})
        gen2 = _mock_gen(body)
        gen2.update({"elapsed_time": 1.0, "tps": 20.0, "ttft": 0.2,
                     "response_tokens": 20, "thinking_tokens": 0, "prompt_tokens": 40})
        client.generate_completion = AsyncMock(side_effect=[gen1, gen2])
        bench = BFCLBenchmark(MagicMock(), client, quick_test=True)
        sample = {"id": "mt_0", "category": "multi_turn", "multi_turn": True,
                  "question": [[{"content": "go"}], [{"content": "back"}]],
                  "answer": [["cd(documents)"], ["cd(documents)"]]}
        with patch("backend.benchmarks.bfcl.multi_turn_simplified_checker",
                   return_value={"valid": True}):
            res = _run_async(bench.evaluate_sample(sample, {"temperature": 0.0}, "t"))
        sd = res["scoring_details"]
        assert sd["category"] == "multi_turn"
        assert len(sd["turns"]) == 2
        assert all("tps" in t and "prompt_tokens" in t for t in sd["turns"])
        # tokens/elapsed throughput (40/3), not averaged per-turn TPS (15)
        assert abs(res["tps"] - 40 / 3) < 1e-9
        assert res["ttft"] == 0.5  # first turn's latency
        assert res["prompt_tokens"] == 70


# ── IFEval / LCM / NIAHS / uncensor ────────────────────────────────

class TestSmallFixes:
    def test_ifeval_task_id_str_and_empty(self):
        from backend.benchmarks.ifeval import IFEvalBenchmark
        bench = IFEvalBenchmark(MagicMock(), MagicMock(), quick_test=True)
        ds = [{"key": 1000, "prompt": "p", "instruction_id_list": [], "kwargs": []}]
        with patch.object(IFEvalBenchmark, "load_dataset", return_value=None):
            pass
        # task_id coercion via load path
        import backend.benchmarks.ifeval as mod
        with patch.object(mod.BaseBenchmark, "_load_json_cached", return_value=ds):
            with patch.object(mod.BaseBenchmark, "_resolve_dataset", return_value="x"):
                loaded = bench.load_dataset()
        assert loaded[0]["task_id"] == "1000"
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen(""))
        bench2 = IFEvalBenchmark(MagicMock(), client, quick_test=True)
        res = _run_async(bench2.evaluate_sample(
            {"task_id": "1", "prompt": "p", "instruction_id_list": [], "kwargs": []},
            {"temperature": 0.0}, "t"))
        assert res["correct"] is False

    def test_lcm_empty_expected(self):
        from backend.benchmarks.long_context_memory import LongContextMemoryBenchmark
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen("a"))
        bench = LongContextMemoryBenchmark(MagicMock(), client, quick_test=True)
        res = _run_async(bench.evaluate_sample(
            {"task_id": "l/0", "context": "c", "question": "q?", "answer": "a"},
            {"temperature": 0.0}, "t"))
        assert res["correct"] is False

    def test_niahs_category(self):
        import json as _json
        from backend.benchmarks.niahs import NIAHSBenchmark
        bench = NIAHSBenchmark(MagicMock(), MagicMock(), quick_test=True)
        ds = bench.load_dataset()
        assert len(ds) == 3
        assert all(s["task_id"].startswith("niahs_run") for s in ds)

    def test_uncensor_empty_keywords(self):
        from backend.benchmarks.uncensor import UncensorBenchBenchmark
        bench = UncensorBenchBenchmark(MagicMock(), MagicMock(), quick_test=True)
        out = bench._score_uncensor("hello world", [])
        assert out["correct"] is False


# ── multi-turn base guards ─────────────────────────────────────────

class TestTurnGuards:
    def test_ensure_user_first(self):
        from backend.benchmarks.multi_turn_base import MultiTurnBenchmark
        conv = [{"role": "system", "content": "s"},
                {"role": "assistant", "content": "hi"},
                {"role": "tool", "content": "x"},
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"}]
        out = MultiTurnBenchmark._ensure_user_first(conv)
        assert out[0]["role"] == "system"
        assert out[1] == {"role": "user", "content": "q"}

    def test_ensure_user_first_no_system(self):
        from backend.benchmarks.multi_turn_base import MultiTurnBenchmark
        conv = [{"role": "assistant", "content": "hi"},
                {"role": "user", "content": "q"}]
        out = MultiTurnBenchmark._ensure_user_first(conv)
        assert out[0]["role"] == "user"
