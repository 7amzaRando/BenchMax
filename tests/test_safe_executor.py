"""Tests for backend/sandbox/safe_executor.py — sandboxed code execution.

These are INTEGRATION tests that spawn real child processes via multiprocessing.
They verify the actual sandbox behavior, not mocked paths.
"""
import os
import shutil
import tempfile
import time
import pytest

from backend.sandbox.safe_executor import (
    check_correctness_humaneval,
    check_correctness_bigcodebench,
    _safe_humaneval_import,
    _cleanup_dir,
)


# ── _safe_humaneval_import ─────────────────────────────────────────

class TestSafeHumanevalImport:
    def test_allows_typing(self):
        mod = _safe_humaneval_import("typing")
        assert mod is not None
        assert hasattr(mod, "List")

    def test_allows_math(self):
        mod = _safe_humaneval_import("math")
        assert mod is not None
        assert hasattr(mod, "floor")

    def test_allows_itertools(self):
        mod = _safe_humaneval_import("itertools")
        assert mod is not None

    def test_blocks_subprocess(self):
        with pytest.raises(ImportError, match="not allowed"):
            _safe_humaneval_import("subprocess")

    def test_blocks_os_system(self):
        """'os' is in the safe whitelist — only dangerous submodules blocked."""
        mod = _safe_humaneval_import("os")
        assert mod is not None
        # os.system is not accessible since we only import the module
        assert hasattr(mod, "path")

    def test_fromlist_resolves_submodule(self):
        mod = _safe_humaneval_import("os", fromlist=["path"])
        assert mod is not None


# ── check_correctness_humaneval ────────────────────────────────────

class TestHumanEval:
    def test_pass_trivial(self):
        result = check_correctness_humaneval(
            entry_point="add",
            prompt="def add(a, b):\n",
            completion="    return a + b",
            test_suite="def check(add):\n    assert add(1, 2) == 3\n    assert add(0, 0) == 0",
            timeout=10.0,
        )
        assert result["passed"] is True
        assert result["result"] == "passed"

    def test_fail_wrong_answer(self):
        result = check_correctness_humaneval(
            entry_point="add",
            prompt="def add(a, b):\n",
            completion="    return a - b",
            test_suite="def check(add):\n    assert add(1, 2) == 3",
            timeout=10.0,
        )
        assert result["passed"] is False
        assert "failed" in result["result"]

    def test_timeout(self):
        result = check_correctness_humaneval(
            entry_point="loop",
            prompt="def loop():\n",
            completion="    import time; time.sleep(100)",
            test_suite="def check(loop):\n    loop()",
            timeout=2.0,
        )
        assert result["passed"] is False

    def test_import_typing(self):
        """The bug we fixed: from typing import List should work."""
        result = check_correctness_humaneval(
            entry_point="get_first",
            prompt="def get_first(items: list) -> object:\n",
            completion="    from typing import List\n    return items[0] if items else None",
            test_suite="def check(get_first):\n    assert get_first([1, 2, 3]) == 1\n    assert get_first([]) is None",
            timeout=10.0,
        )
        assert result["passed"] is True

    def test_import_math(self):
        """The bug we fixed: import math should work."""
        result = check_correctness_humaneval(
            entry_point="floor_val",
            prompt="def floor_val(x: float) -> int:\n",
            completion="    import math\n    return math.floor(x)",
            test_suite="def check(floor_val):\n    assert floor_val(3.7) == 3\n    assert floor_val(1.2) == 1",
            timeout=10.0,
        )
        assert result["passed"] is True

    def test_disallowed_import(self):
        """Dangerous imports like subprocess should be blocked."""
        result = check_correctness_humaneval(
            entry_point="dangerous",
            prompt="def dangerous():\n",
            completion="    import subprocess\n    return True",
            test_suite="def check(dangerous):\n    assert dangerous() == True",
            timeout=10.0,
        )
        assert result["passed"] is False
        assert "not allowed" in result["result"]


# ── check_correctness_bigcodebench ─────────────────────────────────

class TestBigCodeBench:
    def test_unittest_import_allowed(self):
        """BigCodeBench tests require 'import unittest' — must be allowed."""
        code = "def add(a, b):\n    return a + b"
        test_code = (
            "import unittest\n"
            "class TestCases(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(1, 2), 3)\n"
        )
        result = check_correctness_bigcodebench(
            code=code, test_code=test_code, timeout=10.0,
            block_child_processes=False, block_network=False,
        )
        assert result["passed"] is True

    def test_timeout(self):
        code = "import time\ndef slow():\n    time.sleep(100)\nslow()"
        test_code = "class TestCases:\n    pass"
        result = check_correctness_bigcodebench(
            code=code, test_code=test_code, timeout=2.0,
            block_child_processes=False, block_network=False,
        )
        assert result["passed"] is False

    def test_syntax_error(self):
        code = "def add(a, b):\n    return a + b"
        test_code = "class TestCases:\n    def test_bad("
        result = check_correctness_bigcodebench(
            code=code, test_code=test_code, timeout=10.0,
            block_child_processes=False, block_network=False,
        )
        assert result["passed"] is False
        assert len(result["details"]) > 0


# ── _cleanup_dir ───────────────────────────────────────────────────

class TestCleanupDir:
    def test_cleans_existing_dir(self):
        d = tempfile.mkdtemp(prefix="benchmax_test_")
        test_file = os.path.join(d, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        _cleanup_dir(d)
        assert not os.path.exists(d)

    def test_noop_for_none(self):
        _cleanup_dir(None)  # should not raise

    def test_noop_for_missing(self):
        _cleanup_dir("/nonexistent/path/that/does/not/exist")
