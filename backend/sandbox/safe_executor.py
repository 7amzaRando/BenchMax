"""Safe code execution sandbox for benchmarks.

Docker-only: all LLM-generated code runs inside the benchmax-sandbox
container (--cap-drop ALL, --network none, no-new-privileges). There is
no host fallback — if Docker is unavailable or the daemon is not running,
the benchmark fails with a clear RuntimeError. The in-container executor
(import hooks, stdio shims, per-language runners) lives in
backend/sandbox/container_runner.py, which is baked into the image; this
module only maps a check to a container job, creates the parent-owned
tmpdir, and cleans it up afterwards.

Temp directories are always created in the PARENT process and cleaned up
in the parent's finally block, guaranteeing deletion even when the child
is killed via TerminateProcess.
"""

import logging
import os
import secrets
import shutil
import tempfile
from typing import Dict, Any

from backend.config import SANDBOX_USE_DOCKER

logger = logging.getLogger(__name__)

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


def _run_child_in_sandbox(target_func, args, timeout, block_child_processes, block_network):
    """Common pattern: create tmpdir in parent, run child, clean up in parent.

    Docker-only: all code execution runs in the benchmax-sandbox container.
    If Docker is unavailable or the daemon is not running, the benchmark fails
    with a clear error.
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


# Named executor keys for _run_child_in_sandbox. The functions are never
# executed on the host — only their __name__ selects the container job.
def _unsafe_execute_humaneval(*args):
    raise RuntimeError("Host execution removed — Docker-only (benchmax-sandbox).")


def _unsafe_execute_bigcodebench(*args):
    raise RuntimeError("Host execution removed — Docker-only (benchmax-sandbox).")


def _unsafe_execute_livecodebench(*args):
    raise RuntimeError("Host execution removed — Docker-only (benchmax-sandbox).")


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


def check_correctness_aider(sample, edited_code, timeout=300) -> Dict[str, Any]:
    """Run an Aider Polyglot sample's tests in the sandbox container.

    Docker-only: all code execution runs in the benchmax-sandbox container.
    If Docker is unavailable or the daemon is not running, the benchmark fails
    with a clear error.
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

    try:
        result = run_aider_in_container(sample, edited_code, tmpdir, timeout)
        return result
    except Exception as e:
        raise RuntimeError(f"Docker Aider execution failed: {e}") from e
    finally:
        _cleanup_dir(tmpdir)
