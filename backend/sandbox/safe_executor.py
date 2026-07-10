import contextlib
import faulthandler
import io
import logging
import multiprocessing
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import types
from typing import Dict, Any, List

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
    if platform.system() == "Windows":
        timer = threading.Timer(seconds, lambda: (_ for _ in ()).throw(TimeoutException("Timed out!")))
        timer.daemon = True
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
    else:
        def handler(signum, frame):
            raise TimeoutException("Timed out!")
        signal.setitimer(signal.ITIMER_REAL, seconds)
        signal.signal(signal.SIGALRM, handler)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)


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

    import builtins
    builtins.exit = None
    builtins.quit = None

    os.environ["OMP_NUM_THREADS"] = "1"

    os.kill = None
    os.system = None
    os.putenv = None
    os.remove = None
    os.removedirs = None
    os.rmdir = None
    os.fchdir = None
    os.setuid = None
    os.fork = None
    os.forkpty = None
    os.killpg = None
    os.rename = None
    os.renames = None
    os.truncate = None
    os.replace = None
    os.unlink = None
    os.fchmod = None
    os.fchown = None
    os.chmod = None
    os.chown = None
    os.chroot = None
    os.lchflags = None
    os.lchmod = None
    os.lchown = None
    os.getcwd = None
    os.chdir = None

    shutil.rmtree = None
    shutil.move = None
    shutil.chown = None

    subprocess.Popen = None

    __builtins__["help"] = None

    sys.modules["ipdb"] = None
    sys.modules["joblib"] = None
    sys.modules["resource"] = None
    sys.modules["psutil"] = None
    sys.modules["tkinter"] = None


def _unsafe_execute_humaneval(
    entry_point: str,
    prompt: str,
    completion: str,
    test_suite: str,
    timeout: float,
    result_container: list,
):
    with _create_tempdir():
        import os as _os
        import shutil as _shutil
        rmtree = _shutil.rmtree
        rmdir = _os.rmdir
        chdir = _os.chdir

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

        _shutil.rmtree = rmtree
        _os.rmdir = rmdir
        _os.chdir = chdir


def _unsafe_execute_bigcodebench(
    entry_point: str,
    code: str,
    test_code: str,
    timeout: float,
    result_container: list,
    details_container: list,
):
    with _create_tempdir():
        import os as _os
        import shutil as _shutil
        rmtree = _shutil.rmtree
        rmdir = _os.rmdir
        chdir = _os.chdir

        _reliability_guard()

        module_name = "__test__"
        new_module = types.ModuleType(module_name)
        new_module.__dict__.update({
            "__builtins__": __builtins__,
            "__file__": f"{module_name}.py",
            "__package__": None,
            "__doc__": None,
            "sys": sys,
            "os": _os,
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

        _shutil.rmtree = rmtree
        _os.rmdir = rmdir
        _os.chdir = chdir


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
    entry_point: str,
    code: str,
    test_code: str,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    manager = multiprocessing.Manager()
    result = manager.list()
    details = manager.list()

    p = multiprocessing.Process(
        target=_unsafe_execute_bigcodebench,
        args=(entry_point, code, test_code, timeout, result, details),
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
