"""Safe code execution sandbox for benchmarks.

Uses Windows Job Objects and process mitigation policies to restrict
what LLM-generated code can do during execution. Prevents:
- Network access
- File system access outside sandbox
- Child process creation (cmd.exe, powershell.exe, subprocess)
- Dangerous Windows privileges

Temp directories are always created in the PARENT process and cleaned up
in the parent's finally block, guaranteeing deletion even when the child
is killed via TerminateProcess.
"""

import ast
import builtins
import contextlib
import faulthandler
import importlib
import io
import json
import logging
import os
import re
import secrets
import shutil
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch

logger = logging.getLogger(__name__)

# Import sandbox modules (Windows-only)
try:
    from backend.sandbox.job_sandbox import JobSandbox
    from backend.sandbox.appcontainer import (
        create_locked_down_sandbox,
        create_aider_sandbox,
        write_runner_script,
        write_run_config,
        parse_appcontainer_result,
    )
    from backend.config import (
        SANDBOX_ENABLED,
        SANDBOX_MEMORY_LIMIT_MB,
        SANDBOX_CPU_TIME_SEC,
        SANDBOX_USE_APPCONTAINER,
        SANDBOX_USE_DOCKER,
    )
    SANDBOX_AVAILABLE = True
except ImportError:
    SANDBOX_AVAILABLE = False
    SANDBOX_USE_APPCONTAINER = False
    SANDBOX_USE_DOCKER = False
    logger.debug("Sandbox modules not available (non-Windows or missing dependencies)")

# Docker executor (cross-platform)
try:
    from backend.sandbox.docker_executor import (
        run_in_container,
        run_aider_in_container,
        _docker_available as docker_daemon_running,
    )
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger.debug("Docker executor not available")


class TimeoutException(Exception):
    pass


class WriteOnlyStringIO(io.StringIO):
    def read(self, *args, **kwargs):
        raise OSError
    def readline(self, *args, **kwargs):
        raise OSError
    def readable(self):
        return False


class _LCBBufWrapper:
    """Byte-level buffer wrapper around a StringIO for stdin/stdout.buffer compat."""

    def __init__(self, sio):
        self._sio = sio

    def write(self, b):
        if isinstance(b, (bytes, bytearray)):
            self._sio.write(b.decode("utf-8", errors="replace"))
            return len(b)
        self._sio.write(str(b))
        return len(str(b))

    def read(self, n=-1):
        return self._sio.read(n).encode("utf-8")

    def readline(self, limit=-1):
        return self._sio.readline(limit).encode("utf-8")

    def readlines(self, hint=-1):
        return [l.encode("utf-8") for l in self._sio.readlines(hint)]

    def flush(self):
        pass

    def getvalue(self):
        return self._sio.getvalue().encode("utf-8")


class _LCBStdIO(io.StringIO):
    """StringIO with .buffer attribute for binary I/O in LiveCodeBench stdin/stdout."""

    @property
    def buffer(self):
        return _LCBBufWrapper(self)


@contextlib.contextmanager
def _time_limit(seconds: float):
    """No-op context manager. Actual timeout is enforced by the parent via
    p.join(timeout) + p.kill(). On Windows, threading.Timer cannot raise in
    another thread, so per-code-block timeout is not feasible. The process-level
    timeout in _run_child_in_sandbox() is the real safety net."""
    yield


@contextlib.contextmanager
def _swallow_io():
    stream = WriteOnlyStringIO()
    old_stdin = sys.stdin
    sys.stdin = WriteOnlyStringIO()
    with contextlib.redirect_stdout(stream):
        with contextlib.redirect_stderr(stream):
            yield
    sys.stdin = old_stdin


def _reliability_guard():
    faulthandler.disable()
    os.environ["OMP_NUM_THREADS"] = "1"


# Standard library modules allowed in sandboxed HumanEval execution.
# The real security boundary is the separate process + Job Object sandbox;
# this whitelist is defense-in-depth to let models use common imports.
_HUMANEVAL_SAFE_MODULES = frozenset({
    "array", "bisect", "builtins", "calendar", "collections", "colorsys",
    "copy", "datetime", "decimal", "enum", "fractions", "functools",
    "hashlib", "heapq", "hmac", "html", "io", "inspect", "itertools",
    "json", "math", "operator", "os", "pathlib", "platform", "random",
    "re", "socket", "statistics", "string", "struct", "sys", "textwrap",
    "time", "typing", "unicodedata", "uuid", "xml",
})


_HUMANEVAL_SAFE_PRIVATE = frozenset({"_json", "_heapq", "_bisect", "_collections", "_functools", "_struct", "_datetime", "_random", "_string", "_operator", "_hashlib", "_hmac", "_statistics", "_decimal"})

def _safe_humaneval_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Allow only standard library imports in HumanEval sandbox.

    __import__(name, globals, locals, fromlist, level) is the standard
    signature — importlib.import_module only takes (name, package, level),
    so we translate manually.
    """
    if name in _HUMANEVAL_SAFE_MODULES or name in _HUMANEVAL_SAFE_PRIVATE:
        mod = importlib.import_module(name)
        # fromlist means "from X import Y" — walk subpackages as needed
        if fromlist:
            for attr in fromlist:
                if attr == "*":
                    continue
                try:
                    getattr(mod, attr)
                except AttributeError:
                    # e.g. from os import path → import os.path
                    importlib.import_module(f"{name}.{attr}")
        return mod
    raise ImportError(f"Import of '{name}' is not allowed in HumanEval sandbox")


# Modules that can spawn processes or otherwise escape the sandbox even with
# Job Object mitigations applied. Blocked as defense-in-depth regardless of
# standard-library status. The Job Object sandbox + network/child-process
# mitigation remains the real security boundary.
_LCB_IMPORT_DENY = frozenset({
    "subprocess", "multiprocessing", "ctypes", "code", "codeop",
})


def _safe_lcb_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Allow any standard-library import in the LiveCodeBench sandbox.

    LiveCodeBench solutions occasionally need stdlib modules outside the
    narrower HumanEval whitelist (e.g. cmath, dataclasses, collections.abc),
    so we permit every stdlib module and only block a small denylist of
    process-escaping modules. __import__ has the standard signature, so we
    translate to importlib.import_module manually.
    """
    top = name.split(".")[0]
    if top in _LCB_IMPORT_DENY:
        raise ImportError(f"Import of '{name}' is not allowed in LiveCodeBench sandbox")
    if top not in sys.stdlib_module_names:
        raise ImportError(f"Import of '{name}' is not allowed in LiveCodeBench sandbox (non-stdlib)")
    mod = importlib.import_module(name)
    if fromlist:
        for attr in fromlist:
            if attr == "*":
                # from module import * - skip attribute lookup, module already imported
                continue
            try:
                getattr(mod, attr)
            except AttributeError:
                importlib.import_module(f"{name}.{attr}")
    return mod


def _sanitize_child_env():
    """Remove sensitive env vars from child process to prevent credential leaks."""
    safe_keys = {
        "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
        "PYTHONPATH", "PYTHONHOME", "OMP_NUM_THREADS",
        "SYSTEMDRIVE",
    }
    for key in list(os.environ):
        if key not in safe_keys:
            del os.environ[key]


def _sandbox_guard(block_child_processes: bool = True):
    """Apply sandbox restrictions to the child process."""
    if not SANDBOX_AVAILABLE or not SANDBOX_ENABLED:
        return
    try:
        from backend.sandbox.mitigation import remove_dangerous_privileges
        remove_dangerous_privileges()
        if block_child_processes:
            from backend.sandbox.mitigation import apply_child_process_mitigation
            apply_child_process_mitigation()
    except Exception as e:
        logger.debug("Failed to apply sandbox mitigations: %s", e)


def _create_sandbox(block_child_processes: bool = True, block_network: bool = True):
    """Create a Job Object sandbox for the parent process."""
    if not SANDBOX_AVAILABLE or not SANDBOX_ENABLED:
        return None
    try:
        sandbox = JobSandbox()
        sandbox.set_limits(
            memory_mb=SANDBOX_MEMORY_LIMIT_MB,
            process_count=1 if block_child_processes else 8,
            cpu_time_sec=SANDBOX_CPU_TIME_SEC,
            block_network=block_network,
        )
        return sandbox
    except Exception as e:
        logger.warning("Failed to create Job Object sandbox: %s", e)
        return None


def _cleanup_dir(path: str):
    """Best-effort directory cleanup. Retries once after a short delay for locked files."""
    if not path or not os.path.isdir(path):
        return
    for attempt in range(2):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt == 0:
                import time
                time.sleep(0.5)
            else:
                logger.warning("Could not delete temp dir %s (locked files)", path)
        except Exception as e:
            logger.debug("Unexpected error cleaning up temp dir %s: %s", path, e)
            return


def _sandboxed_open(tmpdir, original_open):
    """Return an open() builtin that blocks writes outside tmpdir."""
    tmpdir_real = os.path.realpath(tmpdir)

    def _open(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if isinstance(mode, str) and ("w" in mode or "a" in mode or "x" in mode):
            if os.path.isabs(path):
                raise PermissionError(f"Write blocked: absolute path not allowed in sandbox: {path}")
            real = os.path.realpath(os.path.join(tmpdir, path))
            if not real.startswith(tmpdir_real + os.sep) and real != tmpdir_real:
                raise PermissionError(f"Write blocked outside sandbox: {path}")
            return original_open(real, *args, **kwargs)
        return original_open(path, *args, **kwargs)

    return _open


def _unsafe_execute_humaneval(
    entry_point, prompt, completion, test_suite, timeout,
    result_container, tmpdir,
):
    _sanitize_child_env()
    _sandbox_guard()
    old_cwd = os.getcwd()
    os.chdir(tmpdir)
    try:
        _reliability_guard()
        check_program = f"{prompt}{completion}\n{test_suite}\ncheck({entry_point})"
        try:
            # NOTE: builtins stripping is defense-in-depth, not a hard security boundary.
            # MRO traversal (object.__subclasses__()) can bypass this filter.
            # The real security boundary is the separate process + Job Object sandbox.
            exec_globals = {"__builtins__": {
                k: v for k, v in vars(builtins).items()
                if k not in ("open", "exec", "eval", "compile")
            }}
            exec_globals["__builtins__"]["__import__"] = _safe_humaneval_import
            with _swallow_io():
                with _time_limit(timeout):
                    exec(check_program, exec_globals)
            result_container.append("passed")
        except TimeoutException:
            result_container.append("timed out")
        except BaseException as e:
            result_container.append(f"failed: {e}")
    finally:
        os.chdir(old_cwd)


def _unsafe_execute_bigcodebench(
    code, test_code, timeout, result_container, tmpdir,
):
    """Target function for bigcodebench sandboxed execution.
    Appends a dict with 'result' and 'details' keys to result_container."""
    _sanitize_child_env()
    _sandbox_guard()
    old_cwd = os.getcwd()
    os.chdir(tmpdir)
    details = []
    try:
        _reliability_guard()

        original_open = builtins.open
        builtins.open = _sandboxed_open(tmpdir, original_open)

        _DENY_BUILTINS = frozenset({
            "open", "exec", "eval", "compile",
            "breakpoint", "exit", "quit", "globals", "locals",
        })
        safe_builtins = {k: v for k, v in vars(builtins).items() if k not in _DENY_BUILTINS}
        safe_builtins["__import__"] = _safe_humaneval_import

        _DENY_OS = frozenset({
            "system", "popen", "execle", "execl", "execlp", "execv", "execve",
            "execvp", "execvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe",
            "spawnv", "spawnve", "spawnvp", "spawnvpe", "fork", "forkpty",
            "kill", "abort", "_exit", "killpg",
        })
        import os as _os_module
        safe_os = types.ModuleType("os")
        for attr in dir(_os_module):
            if attr.startswith("_"):
                continue
            if attr in _DENY_OS:
                continue
            setattr(safe_os, attr, getattr(_os_module, attr))
        safe_os.path = _os_module.path

        module_name = "__test__"
        new_module = types.ModuleType(module_name)
        new_module.__dict__.update({
            "__builtins__": safe_builtins,
            "__file__": f"{module_name}.py",
            "__package__": None,
            "__doc__": None,
            "sys": sys,
            "os": safe_os,
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
                    details.append(f"{test.id()}: {trace}")
                result_container.append({"result": "failed", "details": details})
            else:
                result_container.append({"result": "passed", "details": []})
        except TimeoutException:
            result_container.append({"result": "timed out", "details": []})
        except BaseException as e:
            details.append(str(e))
            result_container.append({"result": "failed", "details": details})
        finally:
            builtins.open = original_open
    finally:
        os.chdir(old_cwd)


_LCB_IMPORTS = (
    "from string import *\nfrom re import *\nfrom datetime import *\n"
    "from collections import *\nfrom heapq import *\nfrom bisect import *\n"
    "from copy import *\nfrom math import *\nfrom random import *\n"
    "from statistics import *\nfrom itertools import *\nfrom functools import *\n"
    "from operator import *\nfrom json import *\n"
    "from typing import *\nimport string\nimport re\n"
    "import datetime\nimport collections\nimport heapq\nimport bisect\nimport copy\n"
    "import math\nimport random\nimport statistics\nimport itertools\nimport functools\n"
    "import operator\nimport io\nimport sys\nimport json\n"
    "sys.setrecursionlimit(50000)\n"
)


def _clean_if_name(code: str) -> str:
    try:
        tree = ast.parse(code)
        last = tree.body[-1]
        if isinstance(last, ast.If) and re.match(r"__name__\s*==\s*['\"]?__main__['\"]?\b", ast.unparse(last.test).strip()):
            before = ast.unparse(ast.Module(body=tree.body[:-1], type_ignores=[])) if tree.body[:-1] else ""
            last_code = ast.unparse(ast.Module(body=last.body, type_ignores=[]))
            return before + "\n" + last_code
    except Exception:
        logger.debug("Failed to strip __main__ guard", exc_info=True)
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
        logger.debug("Failed to wrap code in function", exc_info=True)
        return code


def _has_top_level_yield(code: str) -> bool:
    """Check if code contains yield/yield from at the top level (not inside a function)."""
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, (ast.Yield, ast.YieldFrom)):
                return True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if isinstance(child, (ast.Yield, ast.YieldFrom)):
                    return True
    except Exception:
        pass
    return False


def _unsafe_execute_livecodebench(
    code, input_output, timeout, result_container, tmpdir,
):
    _sanitize_child_env()
    _sandbox_guard()
    old_cwd = os.getcwd()
    os.chdir(tmpdir)
    try:
        _reliability_guard()
        try:
            in_outs = json.loads(input_output)
            inputs = in_outs["inputs"]
            outputs = in_outs["outputs"]
            fn_name = in_outs.get("fn_name")

            _DENY_LCB = frozenset({
                "open", "exec", "eval", "compile",
                "breakpoint", "exit", "quit",
            })

            if fn_name:
                all_inputs = []
                for inp in inputs:
                    unescaped_inp = inp.replace("\\n", "\n").replace("\\t", "\t")
                    args = [json.loads(line) for line in unescaped_inp.split("\n")]
                    all_inputs.append(args)
                all_outputs = [json.loads(out) for out in outputs]

                safe_lcb_builtins = {k: v for k, v in vars(builtins).items() if k not in _DENY_LCB}
                safe_lcb_builtins["__import__"] = _safe_lcb_import
                full_code = _LCB_IMPORTS + "\n" + code
                exec_globals = {"__builtins__": safe_lcb_builtins}
                exec(compile(full_code, "lcb_solution.py", "exec"), exec_globals)

                if re.search(r'\bclass\s+Solution\b', code):
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
                        result_container.append("failed: wrong answer")
                        return
            else:
                clean_code = _clean_if_name(code)
                has_top_level_yield = _has_top_level_yield(clean_code)
                if has_top_level_yield:
                    wrapped_code = _LCB_IMPORTS + "\n" + clean_code
                else:
                    wrapped_code = _wrap_in_function(clean_code)
                safe_lcb_builtins = {k: v for k, v in vars(builtins).items() if k not in _DENY_LCB}
                safe_lcb_builtins["__import__"] = _safe_lcb_import
                exec_globals = {"__builtins__": safe_lcb_builtins}
                exec(compile(wrapped_code, "lcb_solution.py", "exec"), exec_globals)

                if has_top_level_yield:
                    method = None
                else:
                    method = exec_globals.get("wrapped_function")
                if method is None:
                    result_container.append("failed: could not wrap code")
                    return

                for inp_str, expected in zip(inputs, outputs):
                    mock_stdin = _LCBStdIO(inp_str)
                    captured = _LCBStdIO()
                    with patch("sys.stdin", mock_stdin), patch("sys.stdout", captured):
                        with _time_limit(timeout):
                            method()
                    actual = captured.getvalue()
                    expected_lines = [l.strip() for l in expected.strip().split("\n") if l.strip()]
                    actual_lines = [l.strip() for l in actual.strip().split("\n") if l.strip()]
                    if expected_lines != actual_lines:
                        result_container.append("failed: output mismatch")
                        return

            result_container.append("passed")
        except TimeoutException:
            result_container.append("timed out")
        except BaseException as e:
            result_container.append(f"failed: {e}")
    finally:
        os.chdir(old_cwd)


def _unsafe_execute_aider(func, args, kwargs, result_container, tmpdir):
    """Target function for aider sandboxed execution."""
    _sanitize_child_env()
    _sandbox_guard(block_child_processes=False)
    _reliability_guard()
    try:
        result = func(*args, tmpdir=tmpdir, **kwargs)
        result_container.append(result)
    except Exception as e:
        result_container.append({"success": False, "stdout": "", "stderr": "",
                                 "error": f"Sandbox execution error: {e}"})


def _run_in_appcontainer(target_func, args, timeout, tmpdir,
                          block_network, run_id=None):
    """Run child process inside Windows AppContainer.

    Writes target function code to a temp script, launches python.exe
    inside the AppContainer, captures result via JSON file.

    Falls back to Job Objects on any failure.
    """

    # Determine which target function module/function to call
    func_module = target_func.__module__
    func_name = target_func.__name__

    # Create AppContainer sandbox
    try:
        if block_network:
            sbx = create_locked_down_sandbox(tmpdir, run_id or 0)
        else:
            runtimes_dir = Path(__file__).parents[2] / ".runtimes"
            sbx = create_aider_sandbox(tmpdir, str(runtimes_dir))

        sbx.setup()

        # Write runner script and config
        runner_path = write_runner_script(tmpdir)
        config_path = write_run_config(tmpdir, func_module, func_name, list(args))

        # Launch python.exe in AppContainer
        t0 = time.monotonic()
        result = sbx.launch(
            python_exe=sys.executable,
            script_path=runner_path,
            args=[config_path, os.path.join(tmpdir, "_result.json")],
            timeout=timeout,
        )
        elapsed = time.monotonic() - t0

        # Parse result
        if result.get("timed_out"):
            logger.warning("AppContainer process timed out after %.1fs", elapsed)
            return ["timed out"]

        if result.get("returncode", -1) != 0:
            stderr = result.get("stderr", "")
            logger.warning("AppContainer process exited with code %d: %s",
                         result.get("returncode"), stderr[:200])

        # Read result from JSON file
        result_file = os.path.join(tmpdir, "_result.json")
        if os.path.exists(result_file):
            with open(result_file, "r") as f:
                result_list = json.load(f)
            logger.debug("AppContainer finished: elapsed=%.2fs result=%s", elapsed,
                        result_list[0] if isinstance(result_list[0], str) else "complex")
            return result_list

        # No result file — try parsing stdout
        stdout = result.get("stdout", "")
        if stdout:
            return parse_appcontainer_result(stdout)

        return ["failed: AppContainer produced no output"]

    except Exception as e:
        logger.warning("AppContainer failed, falling back to Job Objects: %s", e)
        raise  # Let caller handle fallback
    finally:
        try:
            sbx.cleanup()
        except Exception:
            pass


def _run_child_in_sandbox(target_func, args, timeout, block_child_processes, block_network):
    """Common pattern: create tmpdir in parent, run child, clean up in parent.

    Docker-only: all code execution runs in the benchmax-sandbox container.
    If Docker is unavailable or the daemon is not running, the benchmark fails
    with a clear error — no AppContainer or Job Objects fallback.
    """
    tmpdir = tempfile.mkdtemp(prefix=f"bm_{secrets.token_hex(4)}_")

    if not (SANDBOX_USE_DOCKER and DOCKER_AVAILABLE):
        _cleanup_dir(tmpdir)
        raise RuntimeError(
            "Docker is required for code execution but SANDBOX_USE_DOCKER is disabled "
            "or Docker is not installed. Enable Docker or set SANDBOX_USE_DOCKER=True in config.py."
        )

    if not docker_daemon_running():
        _cleanup_dir(tmpdir)
        raise RuntimeError(
            "Docker daemon is not running. Start Docker Desktop or the Docker Engine "
            "before running code-execution benchmarks (HumanEval, BigCodeBench, LiveCodeBench)."
        )

    # Map target_func to container executor name
    func_name = target_func.__name__
    func_to_executor = {
        "_unsafe_execute_humaneval": "humaneval",
        "_unsafe_execute_bigcodebench": "bigcodebench",
        "_unsafe_execute_livecodebench": "livecodebench",
    }
    executor_name = func_to_executor.get(func_name)
    if not executor_name:
        _cleanup_dir(tmpdir)
        raise RuntimeError(f"No Docker executor mapped for function: {func_name}")

    config = {"func": executor_name, "tmpdir": "/workspace"}
    # Add function-specific args
    if executor_name == "humaneval":
        entry_point, prompt, completion, test_suite, exec_timeout = args
        config.update({
            "entry_point": entry_point, "prompt": prompt,
            "completion": completion, "test_suite": test_suite,
            "timeout": exec_timeout,
        })
    elif executor_name == "bigcodebench":
        code, test_code, exec_timeout = args
        config.update({"code": code, "test_code": test_code, "timeout": exec_timeout})
    elif executor_name == "livecodebench":
        code, input_output, exec_timeout = args
        config.update({"code": code, "input_output": input_output, "timeout": exec_timeout})

    try:
        result = run_in_container(config, tmpdir, timeout, block_network)
        return result
    except Exception as e:
        raise RuntimeError(f"Docker execution failed for {executor_name}: {e}") from e
    finally:
        _cleanup_dir(tmpdir)


def check_correctness_humaneval(
    entry_point, prompt, completion, test_suite,
    timeout=10.0, block_child_processes=True, block_network=True,
) -> Dict[str, Any]:
    result = _run_child_in_sandbox(
        _unsafe_execute_humaneval,
        (entry_point, prompt, completion, test_suite, timeout),
        timeout, block_child_processes, block_network,
    )
    if not result:
        result.append("timed out")
    return {"passed": result[0] == "passed", "result": result[0]}


def check_correctness_bigcodebench(
    code, test_code,
    timeout=10.0, block_child_processes=True, block_network=True,
) -> Dict[str, Any]:
    result = _run_child_in_sandbox(
        _unsafe_execute_bigcodebench,
        (code, test_code, timeout),
        timeout, block_child_processes, block_network,
    )
    if not result:
        result.append({"result": "timed out", "details": []})
    entry = result[0]
    # Docker may return a string result ("timed out" / "failed: ...")
    if isinstance(entry, str):
        return {"passed": False, "result": entry, "details": []}
    return {"passed": entry["result"] == "passed", "result": entry["result"], "details": entry["details"]}


def check_correctness_livecodebench(
    code, input_output,
    timeout=10.0, block_child_processes=True, block_network=True,
) -> Dict[str, Any]:
    result = _run_child_in_sandbox(
        _unsafe_execute_livecodebench,
        (code, input_output, timeout),
        timeout, block_child_processes, block_network,
    )
    if not result:
        result.append("timed out")
    return {"passed": result[0] == "passed", "result": result[0]}


def check_correctness_aider(func, *args, timeout=300, **kwargs) -> Dict[str, Any]:
    """Run aider test function in a sandboxed child process.

    Docker-only: all code execution runs in the benchmax-sandbox container.
    If Docker is unavailable or the daemon is not running, the benchmark fails
    with a clear error — no AppContainer or Job Objects fallback.
    """
    tmpdir = tempfile.mkdtemp(prefix=f"bm_aider_{secrets.token_hex(4)}_")

    if not (SANDBOX_USE_DOCKER and DOCKER_AVAILABLE):
        _cleanup_dir(tmpdir)
        raise RuntimeError(
            "Docker is required for Aider Polyglot but SANDBOX_USE_DOCKER is disabled "
            "or Docker is not installed. Enable Docker or set SANDBOX_USE_DOCKER=True in config.py."
        )

    if not docker_daemon_running():
        _cleanup_dir(tmpdir)
        raise RuntimeError(
            "Docker daemon is not running. Start Docker Desktop or the Docker Engine "
            "before running Aider Polyglot."
        )

    # args = (sample, edited_code) from _run_test_in_sandbox
    sample = args[0] if len(args) > 0 else kwargs.get("sample", {})
    edited_code = args[1] if len(args) > 1 else kwargs.get("edited_code", "")

    try:
        result = run_aider_in_container(sample, edited_code, tmpdir, timeout)
        return result
    except Exception as e:
        raise RuntimeError(f"Docker Aider execution failed: {e}") from e
    finally:
        _cleanup_dir(tmpdir)
