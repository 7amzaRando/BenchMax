"""Coverage-gap tests for 9 benchmark modules with zero dedicated scoring tests.

Pure unit tests — no Docker, no LM Studio required.
Follows tests/test_benchmark_sweep_fixes.py + tests/test_benchmarks.py patterns:
MagicMock() db + MagicMock() client with generate_completion mocked to canned
responses, then evaluate_sample() asserted on correct True/False.

Covers: longbench_v2, personal, code_bench, reason_bench, tectonic,
hellaswag, winogrande, commonsenseqa, scorer_base (+ thin: mmmu_pro, lite,
arc, toolcall, long_context_memory).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock


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


def _bench(cls, response):
    client = MagicMock()
    client.generate_completion = AsyncMock(return_value=_mock_gen(response))
    return cls(MagicMock(), client, quick_test=True)


_PARAMS = {"temperature": 0.0, "max_completion_tokens": 10}


# ── longbench_v2: A-D extraction + truncation ───────────────────────

class TestLongBenchV2:
    def _sample(self, **kw):
        base = {
            "task_id": "lb/0",
            "context": "Some long context about Paris.",
            "question": "What city?",
            "choice_A": "Paris", "choice_B": "London",
            "choice_C": "Rome", "choice_D": "Madrid",
            "answer": "A",
            "domain": "qa",
        }
        base.update(kw)
        return base

    def test_correct(self):
        from backend.benchmarks.longbench_v2 import LongBenchV2Benchmark
        bench = _bench(LongBenchV2Benchmark, "A")
        res = _run_async(bench.evaluate_sample(self._sample(), _PARAMS, "t"))
        assert res["correct"] is True

    def test_wrong(self):
        from backend.benchmarks.longbench_v2 import LongBenchV2Benchmark
        bench = _bench(LongBenchV2Benchmark, "C")
        res = _run_async(bench.evaluate_sample(self._sample(), _PARAMS, "t"))
        assert res["correct"] is False

    def test_empty_fails(self):
        from backend.benchmarks.longbench_v2 import LongBenchV2Benchmark
        bench = _bench(LongBenchV2Benchmark, "")
        res = _run_async(bench.evaluate_sample(self._sample(), _PARAMS, "t"))
        assert res["correct"] is False

    def test_truncation_path(self):
        from backend.benchmarks.longbench_v2 import LongBenchV2Benchmark
        bench = _bench(LongBenchV2Benchmark, "B")
        big = "x" * 5000
        sample = self._sample(context=big, answer="B")
        res = _run_async(bench.evaluate_sample(
            sample, {"temperature": 0.0, "max_completion_tokens": 10,
                     "max_context_tokens": 100}, "t"))
        assert res["correct"] is True
        # Truncated prompt must be shorter than the raw 5000-char context.
        assert len(res["prompt"]) < 5000


# ── personal: category handling + .get hardening ────────────────────

class TestPersonal:
    def _sample(self, **kw):
        base = {"task_id": "p/0", "prompt": "Pick B.",
                "type": "mcq", "valid_letters": "A-D",
                "answer": "B", "category": "Knowledge"}
        base.update(kw)
        return base

    def test_correct(self):
        from backend.benchmarks.personal import BenchMaxPersonalBenchmark
        bench = _bench(BenchMaxPersonalBenchmark, "B")
        res = _run_async(bench.evaluate_sample(self._sample(), _PARAMS, "t"))
        assert res["correct"] is True

    def test_wrong(self):
        from backend.benchmarks.personal import BenchMaxPersonalBenchmark
        bench = _bench(BenchMaxPersonalBenchmark, "A")
        res = _run_async(bench.evaluate_sample(self._sample(), _PARAMS, "t"))
        assert res["correct"] is False

    def test_missing_keys_hardened(self):
        # No prompt/category keys — must not raise, category falls back.
        from backend.benchmarks.personal import BenchMaxPersonalBenchmark
        bench = _bench(BenchMaxPersonalBenchmark, "B")
        sample = {"task_id": "p/1", "type": "mcq",
                  "valid_letters": "A-D", "answer": "B"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_empty_fails(self):
        from backend.benchmarks.personal import BenchMaxPersonalBenchmark
        bench = _bench(BenchMaxPersonalBenchmark, "")
        res = _run_async(bench.evaluate_sample(self._sample(), _PARAMS, "t"))
        assert res["correct"] is False


# ── scorer_base subclasses: get_scorer routing ──────────────────────

class TestScorerSubclasses:
    def test_lite_mcq_routing(self):
        from backend.benchmarks.lite import BenchMaxLiteBenchmark
        bench = _bench(BenchMaxLiteBenchmark, "C")
        sample = {"task_id": "l/0", "prompt": "Pick C.",
                  "type": "mcq", "valid_letters": "A-F", "answer": "C",
                  "category": "Code"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_lite_wrong(self):
        from backend.benchmarks.lite import BenchMaxLiteBenchmark
        bench = _bench(BenchMaxLiteBenchmark, "A")
        sample = {"task_id": "l/0", "prompt": "Pick C.",
                  "type": "mcq", "valid_letters": "A-F", "answer": "C",
                  "category": "Code"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is False

    def test_code_bench_exact_routing(self):
        from backend.benchmarks.code_bench import BenchMaxCodeBenchmark
        bench = _bench(BenchMaxCodeBenchmark, "42")
        sample = {"task_id": "c/0", "prompt": "What is 6*7?",
                  "type": "exact", "answer": "42", "category": "Alg"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_code_bench_wrong_exact_fails(self):
        from backend.benchmarks.code_bench import BenchMaxCodeBenchmark
        bench = _bench(BenchMaxCodeBenchmark, "43")
        sample = {"task_id": "c/0", "prompt": "What is 6*7?",
                  "type": "exact", "answer": "42", "category": "Alg"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is False

    def test_reason_bench_exact(self):
        from backend.benchmarks.reason_bench import BenchMaxReasonBenchmark
        bench = _bench(BenchMaxReasonBenchmark, "27")
        sample = {"task_id": "r/0", "prompt": "Count?",
                  "type": "exact", "answer": "27", "category": "Math"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_reason_bench_empty_fails(self):
        from backend.benchmarks.reason_bench import BenchMaxReasonBenchmark
        bench = _bench(BenchMaxReasonBenchmark, "")
        sample = {"task_id": "r/0", "prompt": "Count?",
                  "type": "exact", "answer": "27", "category": "Math"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is False


# ── tectonic: category handling + .get hardening ────────────────────

class TestTectonic:
    def test_correct(self):
        from backend.benchmarks.tectonic import BenchMaxTectonicBenchmark
        bench = _bench(BenchMaxTectonicBenchmark, "B")
        sample = {"task_id": "t/0", "prompt": "Pick B.",
                  "type": "mcq", "valid_letters": "A-F", "answer": "B",
                  "category": "Coding"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_wrong(self):
        from backend.benchmarks.tectonic import BenchMaxTectonicBenchmark
        bench = _bench(BenchMaxTectonicBenchmark, "D")
        sample = {"task_id": "t/0", "prompt": "Pick B.",
                  "type": "mcq", "valid_letters": "A-F", "answer": "B",
                  "category": "Coding"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is False

    def test_missing_category_hardened(self):
        from backend.benchmarks.tectonic import BenchMaxTectonicBenchmark
        bench = _bench(BenchMaxTectonicBenchmark, "B")
        sample = {"task_id": "t/1", "prompt": "Pick B.",
                  "type": "mcq", "valid_letters": "A-F", "answer": "B"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True


# ── GenericMCQ subclasses: shown-options universe + hedge-fails ─────

class TestHellaSWAG:
    def _sample(self):
        return {"task_id": "h/0", "question": "q?",
                "options": ["a", "b", "c", "d"], "answer": "B"}

    def test_correct(self):
        from backend.benchmarks.hellaswag import HellaSWAGBenchmark
        res = _run_async(_bench(HellaSWAGBenchmark, "B").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is True

    def test_hedge_fails(self):
        from backend.benchmarks.hellaswag import HellaSWAGBenchmark
        res = _run_async(_bench(HellaSWAGBenchmark, "A... actually B").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is False

    def test_out_of_range_ignored(self):
        from backend.benchmarks.hellaswag import HellaSWAGBenchmark
        res = _run_async(_bench(HellaSWAGBenchmark, "I think J is nice, but B").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is True

    def test_empty_fails(self):
        from backend.benchmarks.hellaswag import HellaSWAGBenchmark
        res = _run_async(_bench(HellaSWAGBenchmark, "").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is False


class TestWinoGrande:
    def _sample(self):
        return {"task_id": "w/0", "question": "q?",
                "options": ["opt1", "opt2"], "answer": "A"}

    def test_correct(self):
        from backend.benchmarks.winogrande import WinoGrandeBenchmark
        res = _run_async(_bench(WinoGrandeBenchmark, "A").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is True

    def test_wrong(self):
        from backend.benchmarks.winogrande import WinoGrandeBenchmark
        res = _run_async(_bench(WinoGrandeBenchmark, "B").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is False

    def test_stray_C_ignored_in_AB_universe(self):
        from backend.benchmarks.winogrande import WinoGrandeBenchmark
        res = _run_async(_bench(WinoGrandeBenchmark, "C? No — A").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is True


class TestCommonSenseQA:
    def _sample(self):
        return {"task_id": "cs/0", "question": "q?",
                "options": ["a", "b", "c", "d", "e"], "answer": "E"}

    def test_correct(self):
        from backend.benchmarks.commonsenseqa import CommonSenseQABenchmark
        res = _run_async(_bench(CommonSenseQABenchmark, "E").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is True

    def test_hedge_fails(self):
        from backend.benchmarks.commonsenseqa import CommonSenseQABenchmark
        res = _run_async(_bench(CommonSenseQABenchmark, "D or E").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is False


class TestARC:
    def _sample(self):
        return {"task_id": "arc/0", "question": "q?",
                "options": ["a", "b", "c", "d"], "answer": "D"}

    def test_correct(self):
        from backend.benchmarks.arc import ARCBenchmark
        res = _run_async(_bench(ARCBenchmark, "D").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is True

    def test_stray_I_ignored(self):
        # ARC is A-D only; a stray "I" pronoun must not count as the answer.
        from backend.benchmarks.arc import ARCBenchmark
        res = _run_async(_bench(ARCBenchmark, "I believe D").evaluate_sample(
            self._sample(), _PARAMS, "t"))
        assert res["correct"] is True


# ── thin: mmmu_pro / toolcall / long_context_memory ─────────────────

class TestThinCoverage:
    def test_mmmu_correct(self):
        from backend.benchmarks.mmmu_pro import MMMUProBenchmark
        bench = _bench(MMMUProBenchmark, "A")
        sample = {"task_id": "v/0", "question": "q?",
                  "options": ["a", "b", "c", "d"], "answer": "A",
                  "image_paths": []}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_mmmu_images_missing_flag(self):
        from backend.benchmarks.mmmu_pro import MMMUProBenchmark
        bench = _bench(MMMUProBenchmark, "A")
        sample = {"task_id": "v/1", "question": "q?",
                  "options": ["a", "b", "c", "d"], "answer": "A",
                  "image_paths": ["nonexistent_xyz.png"]}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True
        assert res["scoring_details"].get("images_missing") is True

    def test_toolcall_exact(self):
        from backend.benchmarks.toolcall import BenchMaxToolCallBenchmark
        bench = _bench(BenchMaxToolCallBenchmark, "approve_invoice(id=7)")
        sample = {"task_id": "tc/0", "prompt": "Approve it.",
                  "type": "exact", "answer": "approve_invoice(id=7)",
                  "category": "Chains"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_toolcall_wrong(self):
        from backend.benchmarks.toolcall import BenchMaxToolCallBenchmark
        bench = _bench(BenchMaxToolCallBenchmark, "reject_invoice(id=7)")
        sample = {"task_id": "tc/0", "prompt": "Approve it.",
                  "type": "exact", "answer": "approve_invoice(id=7)",
                  "category": "Chains"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is False

    def test_lcm_correct(self):
        from backend.benchmarks.long_context_memory import LongContextMemoryBenchmark
        bench = _bench(LongContextMemoryBenchmark, "Paris")
        sample = {"task_id": "lcm/0", "context": "We visited Paris.",
                  "question": "Where?", "answer": "Paris",
                  "category": "single-hop"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is True

    def test_lcm_empty_expected_false(self):
        from backend.benchmarks.long_context_memory import LongContextMemoryBenchmark
        bench = _bench(LongContextMemoryBenchmark, "anything at all here")
        sample = {"task_id": "lcm/1", "context": "ctx",
                  "question": "q?", "answer": "",
                  "category": "single-hop"}
        res = _run_async(bench.evaluate_sample(sample, _PARAMS, "t"))
        assert res["correct"] is False
