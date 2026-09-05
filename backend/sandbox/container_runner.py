"""Container runner script — executes inside the Docker sandbox.

This script is copied into the Docker image at /opt/benchmax/container_runner.py.
It reads a JSON config from the mounted workspace and dispatches to the appropriate
execution function (humaneval, bigcodebench, livecodebench, or aider).

The key difference from host-side execution: builtins, import whitelisting, and
sandboxed open() all happen INSIDE the container. The host only writes the config
and reads the result.

Timeout enforcement: uses signal.alarm (Linux) since the container runs on Linux.
This provides defense-in-depth on top of the outer Docker subprocess timeout.
"""

import ast
import builtins
import contextlib
import faulthandler
import glob as glob_mod
import importlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


# ── I/O helpers ───────────────────────────────────────────────────

class WriteOnlyStringIO(io.StringIO):
    def read(self, *args, **kwargs):
        raise OSError
    def readline(self, *args, **kwargs):
        raise OSError
    def readable(self):
        return False


class _LCBBufWrapper:
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
    @property
    def buffer(self):
        return _LCBBufWrapper(self)


@contextlib.contextmanager
def _swallow_io():
    stream = WriteOnlyStringIO()
    old_stdin = sys.stdin
    sys.stdin = WriteOnlyStringIO()
    with contextlib.redirect_stdout(stream):
        with contextlib.redirect_stderr(stream):
            yield
    sys.stdin = old_stdin


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _TimeoutError("Execution timed out")


@contextlib.contextmanager
def _time_limit(seconds: float):
    """Enforce per-execution timeout via signal.alarm (Linux only).

    The outer Docker subprocess timeout provides the primary safety net.
    This is defense-in-depth for cases where the container hangs internally.
    """
    if hasattr(signal, "SIGALRM") and seconds > 0:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(int(seconds) + 1)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        yield


def _reliability_guard():
    faulthandler.disable()
    os.environ["OMP_NUM_THREADS"] = "1"


# ── Import whitelists ─────────────────────────────────────────────

_HUMANEVAL_SAFE_MODULES = frozenset({
    "array", "bisect", "builtins", "calendar", "collections", "colorsys",
    "copy", "datetime", "decimal", "enum", "fractions", "functools",
    "hashlib", "heapq", "hmac", "html", "io", "inspect", "itertools",
    "json", "math", "operator", "os", "pathlib", "platform", "random",
    "re", "socket", "statistics", "string", "struct", "sys", "textwrap",
    "time", "typing", "unicodedata", "uuid", "xml",
})

_LCB_IMPORT_DENY = frozenset({
    "subprocess", "multiprocessing", "ctypes", "code", "codeop",
})

# BigCodeBench needs unittest, os, sys, and other stdlib modules for running tests.
# Uses the same deny-list approach as LiveCodeBench.
_BCB_IMPORT_DENY = frozenset({
    "subprocess", "multiprocessing", "ctypes", "code", "codeop",
})


_HUMANEVAL_SAFE_PRIVATE = frozenset({"_json", "_heapq", "_bisect", "_collections", "_functools", "_struct", "_datetime", "_random", "_string", "_operator", "_hashlib", "_hmac", "_statistics", "_decimal"})

def _safe_humaneval_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in _HUMANEVAL_SAFE_MODULES or name in _HUMANEVAL_SAFE_PRIVATE:
        mod = importlib.import_module(name)
        if fromlist:
            for attr in fromlist:
                if attr == "*":
                    continue
                try:
                    getattr(mod, attr)
                except AttributeError:
                    importlib.import_module(f"{name}.{attr}")
        return mod
    raise ImportError(f"Import of '{name}' is not allowed in HumanEval sandbox")


_IMPORTLIB_DENY = frozenset({"importlib"})

def _safe_lcb_import(name, globals=None, locals=None, fromlist=(), level=0):
    top = name.split(".")[0]
    if top in _LCB_IMPORT_DENY or top in _IMPORTLIB_DENY:
        raise ImportError(f"Import of '{name}' is not allowed in LiveCodeBench sandbox")
    if top not in sys.stdlib_module_names:
        raise ImportError(f"Import of '{name}' is not allowed in LiveCodeBench sandbox (non-stdlib)")
    mod = importlib.import_module(name)
    if fromlist:
        for attr in fromlist:
            if attr == "*":
                continue
            try:
                getattr(mod, attr)
            except AttributeError:
                importlib.import_module(f"{name}.{attr}")
    return mod


def _safe_bigcodebench_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Allow stdlib imports for BigCodeBench (needs unittest, os, sys, etc.)."""
    top = name.split(".")[0]
    if top in _BCB_IMPORT_DENY or top in _IMPORTLIB_DENY:
        raise ImportError(f"Import of '{name}' is not allowed in BigCodeBench sandbox")
    if top not in sys.stdlib_module_names:
        raise ImportError(f"Import of '{name}' is not allowed in BigCodeBench sandbox (non-stdlib)")
    mod = importlib.import_module(name)
    if fromlist:
        for attr in fromlist:
            if attr == "*":
                continue
            try:
                getattr(mod, attr)
            except AttributeError:
                importlib.import_module(f"{name}.{attr}")
    return mod


def _sandboxed_open(tmpdir, original_open):
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


# ── HumanEval executor ────────────────────────────────────────────

def _execute_humaneval(config):
    entry_point = config["entry_point"]
    prompt = config["prompt"]
    completion = config["completion"]
    test_suite = config["test_suite"]
    timeout = config.get("timeout", 10.0)
    tmpdir = config["tmpdir"]

    _reliability_guard()
    os.chdir(tmpdir)

    check_program = f"{prompt}{completion}\n{test_suite}\ncheck({entry_point})"
    try:
        exec_globals = {"__builtins__": {
            k: v for k, v in vars(builtins).items()
            if k not in ("open", "exec", "eval", "compile")
        }}
        exec_globals["__builtins__"]["__import__"] = _safe_humaneval_import
        with _swallow_io():
            with _time_limit(timeout):
                exec(check_program, exec_globals)
        return ["passed"]
    except _TimeoutError:
        return ["timed out"]
    except BaseException as e:
        return [f"failed: {e}"]


# ── BigCodeBench executor ─────────────────────────────────────────

def _execute_bigcodebench(config):
    code = config["code"]
    test_code = config["test_code"]
    timeout = config.get("timeout", 10.0)
    tmpdir = config["tmpdir"]

    _reliability_guard()
    os.chdir(tmpdir)
    details = []

    original_open = builtins.open
    builtins.open = _sandboxed_open(tmpdir, original_open)

    _DENY_BUILTINS = frozenset({
        "open", "exec", "eval", "compile",
        "breakpoint", "exit", "quit", "globals", "locals",
    })
    safe_builtins = {k: v for k, v in vars(builtins).items() if k not in _DENY_BUILTINS}
    safe_builtins["__import__"] = _safe_bigcodebench_import

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
            return [{"result": "failed", "details": details}]
        return [{"result": "passed", "details": []}]
    except _TimeoutError:
        return [{"result": "timed out", "details": []}]
    except BaseException as e:
        details.append(str(e))
        return [{"result": "failed", "details": details}]
    finally:
        builtins.open = original_open


# ── LiveCodeBench executor ────────────────────────────────────────

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


def _has_top_level_yield(code: str) -> bool:
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


def _execute_livecodebench(config):
    code = config["code"]
    input_output = config["input_output"]
    timeout = config.get("timeout", 10.0)
    tmpdir = config["tmpdir"]

    _reliability_guard()
    os.chdir(tmpdir)

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
                return ["failed: function not found"]

            for args, expected in zip(all_inputs, all_outputs):
                with _time_limit(timeout):
                    prediction = method(*args)
                if isinstance(prediction, tuple):
                    prediction = list(prediction)
                if prediction != expected:
                    return ["failed: wrong answer"]
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
                return ["failed: could not wrap code"]

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
                    return ["failed: output mismatch"]

        return ["passed"]
    except _TimeoutError:
        return ["timed out"]
    except BaseException as e:
        return [f"failed: {e}"]


# ── Aider Polyglot executor ───────────────────────────────────────

def _java_test_class(src_name):
    stem = os.path.splitext(os.path.basename(src_name))[0]
    if stem.endswith("Test"):
        return stem
    return stem.replace("Test", "") + "Test"


def _execute_aider(config):
    """Run aider test: write workspace, dispatch to language test runner.

    Returns a list with a single dict (to match docker_executor's expected format).
    """
    sample = config["sample"]
    edited_code = config["edited_code"]
    tmpdir = config["tmpdir"]

    _reliability_guard()

    # Write workspace files
    _write_workspace(sample, edited_code, tmpdir)

    # Dispatch to language-specific runner
    lang = sample.get("language", "")
    if lang == "python":
        result = _run_python_test(sample, tmpdir)
    elif lang == "javascript":
        result = _run_javascript_test(sample, tmpdir)
    elif lang == "java":
        result = _run_java_test(sample, tmpdir)
    elif lang == "go":
        result = _run_go_test(sample, tmpdir)
    elif lang == "rust":
        result = _run_rust_test(sample, tmpdir)
    elif lang in ("cpp", "c++"):
        result = _run_cpp_test(sample, tmpdir)
    else:
        result = {"success": False, "stdout": "", "stderr": "",
                  "error": f"Unknown language: {lang}"}
    return [result]


def _write_workspace(sample, edited_code, tmpdir):
    lang = sample.get("language", "")

    def write_file(rel_path, content):
        full = os.path.join(tmpdir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    write_file(sample.get("source_path", ""), edited_code)

    test_content = sample.get("test_code", "")
    if lang == "cpp":
        header_name = os.path.splitext(os.path.basename(sample.get("source_path", "")))[0] + ".h"
        source_name = os.path.basename(sample.get("source_path", ""))
        test_content = re.sub(
            r'#include\s+"' + re.escape(header_name) + r'"',
            '#include "' + source_name + '"',
            test_content,
        )
    write_file(sample.get("test_path", ""), test_content)

    extra_files = sample.get("extra_files") or {}
    for rel_path, content in extra_files.items():
        write_file(rel_path, content)

    if lang == "javascript":
        write_file("babel.config.js",
                   "module.exports = { presets: ['@babel/preset-env'] };\n")
        write_file("package.json", json.dumps({
            "name": "aider-polyglot-js",
            "private": True,
            "jest": {
                "transform": {"^.+\\.jsx?$": "babel-jest"},
            },
        }))

    if lang == "go":
        has_mod = any(k.endswith("go.mod") for k in (extra_files or {}))
        if not has_mod:
            write_file("go.mod", "module aider_polyglot\n\ngo 1.22\n")


def _subprocess_run(cmd, cwd, timeout=120, env=None):
    """Run a subprocess with timeout, return dict with stdout/stderr/returncode."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, env=merged_env,
            encoding="utf-8", errors="replace",
        )
        return {
            "success": proc.returncode == 0,
            "stdout": (proc.stdout or "")[:5000],
            "stderr": (proc.stderr or "")[:2000],
            "error": None if proc.returncode == 0 else f"Exit {proc.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "",
                "error": f"Timeout ({timeout}s)"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": "", "error": str(e)}


def _run_python_test(sample, tmpdir):
    test_name = sample.get("test_path", "")
    module = test_name.replace(os.sep, '.').replace(".py", "")
    return _subprocess_run(
        [sys.executable, "-m", "unittest", module],
        cwd=tmpdir, timeout=120,
    )


def _run_javascript_test(sample, tmpdir):
    node_modules = "/usr/lib/node_modules"
    return _subprocess_run(
        ["npx", "jest", "--no-coverage", "--runInBand"],
        cwd=tmpdir, timeout=120,
        env={"NODE_PATH": node_modules},
    )


def _run_java_test(sample, tmpdir):
    classes_dir = os.path.join(tmpdir, "classes")
    os.makedirs(classes_dir, exist_ok=True)
    junit_jar = "/opt/jars/junit-platform-console-standalone-1.11.4.jar"
    assertj_jar = "/opt/jars/assertj-core-3.27.3.jar"
    sep = ":"

    src_files = glob_mod.glob(os.path.join(tmpdir, "src", "main", "java", "*.java"))
    if not src_files:
        return {"success": False, "stdout": "", "stderr": "",
                "error": "No Java source files found"}

    # Compile main sources
    r = _subprocess_run(
        ["javac", "-d", classes_dir] + src_files,
        cwd=tmpdir, timeout=60,
    )
    if not r["success"]:
        return {"success": False, "stdout": r["stdout"], "stderr": r["stderr"],
                "error": f"javac main failed: {r['error']}"}

    # Compile test sources
    test_files = glob_mod.glob(os.path.join(tmpdir, "src", "test", "java", "*.java"))
    if not test_files:
        return {"success": True, "stdout": "No tests found", "stderr": "", "error": None}

    cp = f"{classes_dir}{sep}{junit_jar}{sep}{assertj_jar}"
    r = _subprocess_run(
        ["javac", "-d", classes_dir, "-cp", cp] + test_files,
        cwd=tmpdir, timeout=60,
    )
    if not r["success"]:
        return {"success": False, "stdout": r["stdout"], "stderr": r["stderr"],
                "error": f"javac test failed: {r['error']}"}

    # Run tests
    test_class = _java_test_class(sample.get("source_path", ""))
    return _subprocess_run(
        ["java", "-jar", junit_jar, "--classpath", cp, "--select-class", test_class],
        cwd=tmpdir, timeout=30,
    )


def _run_go_test(sample, tmpdir):
    go_tmp = os.path.join(tmpdir, ".gotmp")
    os.makedirs(go_tmp, exist_ok=True)
    return _subprocess_run(
        ["go", "test", "./..."],
        cwd=tmpdir, timeout=120,
        env={
            "GOCACHE": os.path.join(tmpdir, ".gocache"),
            "GOPATH": os.path.join(tmpdir, ".gopath"),
            "GOENV": "off",
            "TMPDIR": go_tmp,
        },
    )


def _run_rust_test(sample, tmpdir):
    cargo_home = os.path.join(tmpdir, ".cargo")
    # Cargo is installed to /root/.cargo/bin but container runs as appuser
    # which cannot read /root. Fall back to /opt/cargo if present, else try PATH.
    cargo_bin_dirs = ["/opt/cargo/bin", "/opt/rustup/bin", "/root/.cargo/bin"]
    cargo_path = ""
    for d in cargo_bin_dirs:
        if os.path.exists(os.path.join(d, "cargo")):
            # Check if readable
            try:
                os.listdir(d)
                cargo_path = d
                break
            except PermissionError:
                continue
    env = {"CARGO_HOME": cargo_home}
    if cargo_path:
        env["PATH"] = cargo_path + os.pathsep + os.environ.get("PATH", "")
        env["RUSTUP_HOME"] = os.path.join(os.path.dirname(cargo_path), "..", "rustup") if "rustup" in cargo_path else "/opt/rustup"
    return _subprocess_run(
        ["cargo", "test", "--", "--test-threads=1"],
        cwd=tmpdir, timeout=120,
        env=env,
    )


def _run_cpp_test(sample, tmpdir):
    src_path = sample.get("source_path", "")
    test_file = os.path.basename(src_path).replace('.cpp', '_test.cpp')
    test_path = os.path.join(tmpdir, test_file)
    exe_path = os.path.join(tmpdir, "test")

    # Compile
    r = _subprocess_run(
        ["g++", "-std=c++20", "-DEXERCISM_RUN_ALL_TESTS", "-DEXERCISM_TEST_SUITE",
         "-DCATCH_CONFIG_MAIN", "-I/usr/local/include", "-o", exe_path, test_path],
        cwd=tmpdir, timeout=60,
    )
    if not r["success"]:
        return {"success": False, "stdout": r["stdout"], "stderr": r["stderr"],
                "error": f"g++ compile failed: {r['error']}"}

    # Run
    return _subprocess_run([exe_path], cwd=tmpdir, timeout=30)


# ── Dispatcher ─────────────────────────────────────────────────────

EXECUTORS = {
    "humaneval": _execute_humaneval,
    "bigcodebench": _execute_bigcodebench,
    "livecodebench": _execute_livecodebench,
    "aider": _execute_aider,
}


def main():
    config_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(config_path, "r") as f:
        config = json.load(f)

    func_name = config["func"]
    executor = EXECUTORS.get(func_name)
    if executor is None:
        result = [f"failed: unknown executor '{func_name}'"]
    else:
        try:
            result = executor(config)
        except Exception as e:
            result = [f"failed: {e}"]

    with open(output_path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
