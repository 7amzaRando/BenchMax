"""Regression tests for BigCodeBench + Aider Polyglot scoring fixes.

Pure unit tests — no Docker, no LM Studio required.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _run_async(coro):
    return asyncio.run(coro)


def _mock_gen(response="code"):
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


# ── BigCodeBench body-only wrap ───────────────────────────────────

class TestBCBPrepareCode:
    def test_body_only_wraps_with_prompt_signature(self):
        from backend.benchmarks.bigcodebench import _prepare_bcb_code
        prompt = "Write code starting with:\nimport os\ndef task_func(directory):"
        body = "    import os\n    return os.path.exists(directory)"
        out = _prepare_bcb_code(body, "task_func", prompt)
        assert "def task_func(directory):" in out
        assert "os.path.exists" in out

    def test_full_definition_returned_as_is(self):
        from backend.benchmarks.bigcodebench import _prepare_bcb_code
        code = "def task_func(x):\n    return x"
        assert _prepare_bcb_code(code, "task_func", "prompt") == code

    def test_empty_returns_empty(self):
        from backend.benchmarks.bigcodebench import _prepare_bcb_code
        assert _prepare_bcb_code("", "task_func", "prompt") == ""
        assert _prepare_bcb_code("   ", "task_func", "prompt") == ""

    def test_return_annotation_signature(self):
        from backend.benchmarks.bigcodebench import _prepare_bcb_code
        prompt = "starting with:\nimport os\ndef task_func(src: str, seed: int = 100) -> str:"
        out = _prepare_bcb_code("    return src", "task_func", prompt)
        assert out.startswith("def task_func(src: str, seed: int = 100) -> str:")

    def test_constants_preamble_prepended(self):
        from backend.benchmarks.bigcodebench import _prepare_bcb_code
        prompt = (
            "starting with:\n```\nimport pandas as pd\n# Constants\n"
            "LETTERS = list('abcdefghijklmnopqrstuvwxyz')\n"
            "def task_func(data, letter):\n```"
        )
        out = _prepare_bcb_code("    return 1", "task_func", prompt)
        assert "LETTERS = list('abcdefghijklmnopqrstuvwxyz')" in out
        assert "import pandas as pd" in out


class TestBCBEvaluateSample:
    def test_body_only_scores_via_checker_and_records_category(self):
        from backend.benchmarks.bigcodebench import BigCodeBenchBenchmark
        body = "    return a + b"
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen(body))
        bench = BigCodeBenchBenchmark(MagicMock(), client, quick_test=True)
        sample = {
            "task_id": "t/0",
            "prompt": "Write code starting with:\ndef task_func(a, b):",
            "entry_point": "task_func",
            "test": "class TestCases: pass",
        }
        with patch(
            "backend.benchmarks.bigcodebench.check_correctness_bigcodebench",
            return_value={"passed": True, "result": "passed", "details": []},
        ) as mock_check:
            result = _run_async(
                bench.evaluate_sample(
                    sample,
                    {"temperature": 0.0, "max_completion_tokens": 100},
                    "test",
                )
            )
        assert result["correct"] is True
        # The checker must receive a runnable definition, not the bare body.
        assert "def task_func" in mock_check.call_args.kwargs["code"]
        assert result["scoring_details"] == {"category": "BigCodeBench"}

    def test_hard_preset_records_hard_category(self):
        from backend.benchmarks.bigcodebench import BigCodeBenchBenchmark
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen("def task_func():\n    pass"))
        bench = BigCodeBenchBenchmark(MagicMock(), client, quick_test=True, hard=True)
        sample = {
            "task_id": "t/0",
            "prompt": "p",
            "entry_point": "task_func",
            "test": "",
        }
        result = _run_async(
            bench.evaluate_sample(
                sample, {"temperature": 0.0, "max_completion_tokens": 100}, "test"
            )
        )
        assert result["scoring_details"] == {"category": "BigCodeBench-Hard"}

    def test_empty_answer_is_incorrect(self):
        from backend.benchmarks.bigcodebench import BigCodeBenchBenchmark
        client = MagicMock()
        client.generate_completion = AsyncMock(return_value=_mock_gen(""))
        bench = BigCodeBenchBenchmark(MagicMock(), client, quick_test=True)
        sample = {"task_id": "t/0", "prompt": "p", "entry_point": "task_func", "test": "t"}
        result = _run_async(
            bench.evaluate_sample(
                sample, {"temperature": 0.0, "max_completion_tokens": 100}, "test"
            )
        )
        assert result["correct"] is False
        assert result["error_message"]


# ── BigCodeBench import hook ──────────────────────────────────────

class TestBCBImportHook:
    def test_allows_task_dependencies(self):
        from backend.sandbox.safe_executor import _safe_bigcodebench_import as host_hook
        from backend.sandbox.container_runner import (
            _safe_bigcodebench_import as container_hook,
        )
        for hook in (host_hook, container_hook):
            hook("subprocess")
            hook("unittest")
            hook("importlib")
            hook("os", fromlist=["path"])
            hook("ftplib")

    def test_blocks_process_escape_and_junk(self):
        import pytest
        from backend.sandbox.safe_executor import _safe_bigcodebench_import as host_hook
        from backend.sandbox.container_runner import (
            _safe_bigcodebench_import as container_hook,
        )
        for hook in (host_hook, container_hook):
            for name in ("multiprocessing", "ctypes", "code", "codeop",
                         "nonexistent_pkg_xyz123"):
                with pytest.raises(ImportError):
                    hook(name)

    def test_dotted_import_as_form(self):
        # Regression: `import matplotlib.pyplot as plt` failed with
        # "cannot import name 'pyplot'" because the hook returned the
        # submodule instead of the top module (real __import__ protocol).
        import builtins
        from backend.sandbox.safe_executor import _safe_bigcodebench_import as hook
        g = {"__builtins__": {**vars(builtins), "__import__": hook}}
        exec("import os.path as p\nassert p.join('a', 'b')", g)
        exec("import xml.etree.ElementTree as ET\nassert hasattr(ET, 'fromstring')", g)


# ── Benchmark registration ────────────────────────────────────────

class TestInstantiateBenchmark:
    def test_hard_preset_sets_flag(self):
        from backend.operations import _instantiate_benchmark
        from backend.benchmarks.bigcodebench import BigCodeBenchBenchmark
        bench = _instantiate_benchmark(
            "BigCodeBench-Hard", MagicMock(), MagicMock(), False
        )
        assert isinstance(bench, BigCodeBenchBenchmark)
        assert bench.hard is True

    def test_plain_bench_has_no_hard_flag(self):
        from backend.operations import _instantiate_benchmark
        bench = _instantiate_benchmark(
            "BigCodeBench", MagicMock(), MagicMock(), False
        )
        assert bench.hard is False

    def test_other_benchmarks_unaffected_by_hard_sniff(self):
        # A benchmark whose class has no `hard` param must still instantiate
        # even if its name ever contained "hard".
        from backend.operations import _instantiate_benchmark
        bench = _instantiate_benchmark("HumanEval", MagicMock(), MagicMock(), False)
        assert bench is not None

    def test_bcb_category_backfill(self):
        from backend.operations import _sample_category_for_benchmark
        assert _sample_category_for_benchmark({}, "BigCodeBench") == "BigCodeBench"
        assert (
            _sample_category_for_benchmark({}, "BigCodeBench-Hard")
            == "BigCodeBench-Hard"
        )


# ── Aider Polyglot helpers ────────────────────────────────────────

class TestAiderHelpers:
    def test_java_class_from_test_path(self):
        from backend.benchmarks.aider_polyglot import _java_test_class
        # Regression: Tree.java source gave TreeTest; real class is PovTest.
        assert _java_test_class("src/test/java/PovTest.java") == "PovTest"
        assert _java_test_class("src/test/java/AffineCipherTest.java") == "AffineCipherTest"

    def test_cpp_test_rel_suffix_safe(self):
        from backend.benchmarks.aider_polyglot import _cpp_test_rel
        assert _cpp_test_rel("src/a.cpp") == "src/a_test.cpp"
        # Mid-string ".cpp" must not be replaced.
        assert _cpp_test_rel("my.cpp.lib") == "my.cpp.lib_test.cpp"
        # Dataset test_path wins when provided.
        assert _cpp_test_rel("a.cpp", "nested/t_test.cpp") == "nested/t_test.cpp"

    def test_extract_go_plain_code(self):
        from backend.benchmarks.aider_polyglot import AiderPolyglotBenchmark
        bench = AiderPolyglotBenchmark.__new__(AiderPolyglotBenchmark)
        code = "func Solve(x int) int {\n\treturn x\n}"
        assert "func Solve" in bench._extract_edited_code(code)

    def test_babel_preserved_when_dataset_pins_it(self):
        import tempfile
        import os
        from backend.benchmarks.aider_polyglot import _write_temp_workspace
        sample = {
            "language": "javascript",
            "source_path": "a.js",
            "test_path": "a.spec.js",
            "test_code": "t",
            "extra_files": {
                "babel.config.js": "custom-preset",
                "package.json": '{"custom": true}',
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            _write_temp_workspace(sample, "code", tmp)
            with open(os.path.join(tmp, "babel.config.js")) as f:
                assert f.read() == "custom-preset"
            with open(os.path.join(tmp, "package.json")) as f:
                assert f.read() == '{"custom": true}'
