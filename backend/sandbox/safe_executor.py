import ast
import contextlib
import faulthandler
import io
import json
import logging
import multiprocessing
import os
import platform
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
import types
from typing import Dict, Any, List
from unittest.mock import patch

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    pass


class WriteOnlyStringIO(io.StringIO):
    def read(self, *args, **kwargs):
        raise OSError
    def readline(self, *args, **kwargs):
        raise OSError
    def readable(self):
        return False


@contextlib.contextmanager
def _time_limit(seconds: float):
    # Timeout is handled by outer process-level timeout (p.join(timeout) + p.kill()).
    # On Windows, threading.Timer cannot raise in another thread, so this is a no-op.
    # On Unix, SIGALRM is used but process-level timeout is the real safety net.
    yield


@contextlib.contextmanager
def _swallow_io():
    stream = WriteOnlyStringIO()
    with contextlib.redirect_stdout(stream):
        with contextlib.redirect_stderr(stream):
            yield


@contextlib.contextmanager
def _create_tempdir():
    with tempfile.TemporaryDirectory() as dirname:
        old_cwd = os.getcwd()
        os.chdir(dirname)
        try:
            yield dirname
        finally:
            os.chdir(old_cwd)


def _reliability_guard():
    faulthandler.disable()
    os.environ["OMP_NUM_THREADS"] = "1"


def _unsafe_execute_humaneval(
    entry_point: str,
    prompt: str,
    completion: str,
    test_suite: str,
    timeout: float,
    result_container: list,
):
    with _create_tempdir():
        _reliability_guard()

        check_program = f"{prompt}{completion}\n{test_suite}\ncheck({entry_point})"

        try:
            exec_globals = {}
            with _swallow_io():
                with _time_limit(timeout):
                    exec(check_program, exec_globals)
            result_container.append("passed")
        except TimeoutException:
            result_container.append("timed out")
        except BaseException as e:
            result_container.append(f"failed: {e}")


def _unsafe_execute_bigcodebench(
    code: str,
    test_code: str,
    timeout: float,
    result_container: list,
    details_container: list,
):
    with _create_tempdir():
        _reliability_guard()

        module_name = "__test__"
        new_module = types.ModuleType(module_name)
        new_module.__dict__.update({
            "__builtins__": __builtins__,
            "__file__": f"{module_name}.py",
            "__package__": None,
            "__doc__": None,
            "sys": sys,
            "os": os,
        })

        try:
            full_code = code + "\n" + test_code

            with _swallow_io():
                exec(compile(full_code, f"{module_name}.py", "exec"), new_module.__dict__)
                sys.modules[module_name] = new_module
                TestCases = getattr(new_module, "TestCases")
                loader = unittest.TestLoader()
                suite = loader.loadTestsFromTestCase(TestCases)
                test_result = unittest.TestResult()
                with _time_limit(timeout):
                    suite.run(test_result)

            issues = test_result.failures + test_result.errors
            if issues:
                for test, trace in issues:
                    details_container.append(f"{test.id()}: {trace}")
                result_container.append("failed")
            else:
                result_container.append("passed")
        except TimeoutException:
            result_container.append("timed out")
        except BaseException as e:
            details_container.append(str(e))
            result_container.append("failed")


def check_correctness_humaneval(
    entry_point: str,
    prompt: str,
    completion: str,
    test_suite: str,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    manager = multiprocessing.Manager()
    result = manager.list()

    p = multiprocessing.Process(
        target=_unsafe_execute_humaneval,
        args=(entry_point, prompt, completion, test_suite, timeout, result),
    )
    p.start()
    p.join(timeout=timeout + 5)
    if p.is_alive():
        p.kill()
        p.join()

    if not result:
        result.append("timed out")

    return {
        "passed": result[0] == "passed",
        "result": result[0],
    }


def check_correctness_bigcodebench(
    code: str,
    test_code: str,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    manager = multiprocessing.Manager()
    result = manager.list()
    details = manager.list()

    p = multiprocessing.Process(
        target=_unsafe_execute_bigcodebench,
        args=(code, test_code, timeout, result, details),
    )
    p.start()
    p.join(timeout=timeout + 5)
    if p.is_alive():
        p.kill()
        p.join()

    if not result:
        result.append("timed out")

    return {
        "passed": result[0] == "passed",
        "result": result[0],
        "details": list(details),
    }


_LCB_IMPORTS = (
    "from string import *\nfrom re import *\nfrom datetime import *\n"
    "from collections import *\nfrom heapq import *\nfrom bisect import *\n"
    "from copy import *\nfrom math import *\nfrom random import *\n"
    "from statistics import *\nfrom itertools import *\nfrom functools import *\n"
    "from operator import *\nfrom io import *\nfrom json import *\n"
    "from builtins import *\nfrom typing import *\nimport string\nimport re\n"
    "import datetime\nimport collections\nimport heapq\nimport bisect\nimport copy\n"
    "import math\nimport random\nimport statistics\nimport itertools\nimport functools\n"
    "import operator\nimport io\nimport sys\nimport json\n"
    "sys.setrecursionlimit(50000)\n"
)

_LEETCODE_IMPORTS = (
    "from typing import *\nimport math\nimport sys\nimport collections\n"
    "import heapq\nimport bisect\nimport itertools\nimport functools\n"
    "import random\nimport statistics\n"
)


def _clean_if_name(code: str) -> str:
    try:
        tree = ast.parse(code)
        last = tree.body[-1]
        if isinstance(last, ast.If) and ast.unparse(last.test).strip() == "__name__ == '__main__'":
            before = ast.unparse(ast.Module(body=tree.body[:-1], type_ignores=[])) if tree.body[:-1] else ""
            last_code = ast.unparse(ast.Module(body=last.body, type_ignores=[]))
            return before + "\n" + last_code
    except Exception:
        pass
    return code


def _wrap_in_function(code: str) -> str:
    try:
        tree = ast.parse(code)
        stmts = tree.body
        func = ast.FunctionDef(
            name="wrapped_function",
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=stmts,
            decorator_list=[],
            lineno=-1,
        )
        return _LCB_IMPORTS + "\n" + ast.unparse(func)
    except Exception:
        return code


def _unsafe_execute_livecodebench(
    code: str,
    input_output: str,
    timeout: float,
    result_container: list,
):
    with _create_tempdir():
        _reliability_guard()

        try:
            in_outs = json.loads(input_output)
            inputs = in_outs["inputs"]
            outputs = in_outs["outputs"]
            fn_name = in_outs.get("fn_name")

            if fn_name:
                all_inputs = []
                for inp in inputs:
                    args = [json.loads(line) for line in inp.split("\n")]
                    all_inputs.append(args)
                all_outputs = [json.loads(out) for out in outputs]

                full_code = _LCB_IMPORTS + "\n" + code
                exec_globals = {}
                exec(compile(full_code, "lcb_solution.py", "exec"), exec_globals)

                if "Solution" in code:
                    sol = exec_globals.get("Solution")
                    if sol:
                        instance = sol()
                        method = getattr(instance, fn_name, None)
                    else:
                        method = None
                else:
                    method = exec_globals.get(fn_name)

                if method is None:
                    result_container.append("failed: function not found")
                    return

                for args, expected in zip(all_inputs, all_outputs):
                    with _time_limit(timeout):
                        prediction = method(*args)
                    if isinstance(prediction, tuple):
                        prediction = list(prediction)
                    if prediction != expected:
                        result_container.append(f"failed: wrong answer")
                        return
            else:
                clean_code = _clean_if_name(code)
                wrapped_code = _wrap_in_function(clean_code)
                exec_globals = {}
                exec(compile(wrapped_code, "lcb_solution.py", "exec"), exec_globals)
                method = exec_globals.get("wrapped_function")
                if method is None:
                    result_container.append("failed: could not wrap code")
                    return

                for inp_str, expected in zip(inputs, outputs):
                    mock_stdin = io.StringIO(inp_str)
                    captured = io.StringIO()
                    with patch("sys.stdin", mock_stdin), patch("sys.stdout", captured):
                        with _time_limit(timeout):
                            method()
                    actual = captured.getvalue()
                    expected_lines = [l.strip() for l in expected.strip().split("\n") if l.strip()]
                    actual_lines = [l.strip() for l in actual.strip().split("\n") if l.strip()]
                    if expected_lines != actual_lines:
                        result_container.append(f"failed: output mismatch")
                        return

            result_container.append("passed")
        except TimeoutException:
            result_container.append("timed out")
        except BaseException as e:
            result_container.append(f"failed: {e}")


def check_correctness_livecodebench(
    code: str,
    input_output: str,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    manager = multiprocessing.Manager()
    result = manager.list()

    p = multiprocessing.Process(
        target=_unsafe_execute_livecodebench,
        args=(code, input_output, timeout, result),
    )
    p.start()
    p.join(timeout=timeout + 5)
    if p.is_alive():
        p.kill()
        p.join()

    if not result:
        result.append("timed out")

    return {
        "passed": result[0] == "passed",
        "result": result[0],
    }
