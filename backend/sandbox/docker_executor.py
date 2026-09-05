"""Docker-based sandbox for code execution isolation.

Uses a single combined Docker image with all runtimes (Python, Node, GCC,
Java, Go, Rust) for cross-language benchmark execution. Replaces the 6
separate images with one unified image.

Architecture:
    1. Host writes config JSON to tmpdir
    2. Host starts container with tmpdir mounted at /workspace
    3. Container runs /opt/benchmax/container_runner.py which reads config,
       executes code, writes result JSON
    4. Host reads result JSON from tmpdir
    5. Host cleans up tmpdir

Requires Docker Desktop (Windows/Mac) or Docker Engine (Linux).

Build: docker build -t benchmax-sandbox -f backend/docker/Dockerfile .
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

IMAGE_NAME = "benchmax-sandbox"
DOCKERFILE_DIR = str(Path(__file__).parents[2] / "backend" / "docker")
CONTAINER_RUNNER = "/opt/benchmax/container_runner.py"


def _docker_available() -> bool:
    """Check if Docker CLI is available and daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _image_exists() -> bool:
    """Check if the benchmax-sandbox image exists locally."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", IMAGE_NAME],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_image() -> Dict[str, Any]:
    """Build the benchmax-sandbox Docker image.

    Returns dict with 'success' bool and optional 'error' message.
    """
    if not _docker_available():
        return {"success": False, "error": "Docker is not available or not running"}

    project_root = str(Path(__file__).parents[2])
    logger.info("Building Docker image %s from %s", IMAGE_NAME, DOCKERFILE_DIR)

    try:
        result = subprocess.run(
            ["docker", "build", "-t", IMAGE_NAME, "-f",
             os.path.join(DOCKERFILE_DIR, "Dockerfile"), project_root],
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            logger.info("Docker image built successfully")
            return {"success": True}
        else:
            error = result.stderr[-500:] if result.stderr else "Build failed"
            logger.error("Docker build failed: %s", error)
            return {"success": False, "error": error}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Docker build timed out (600s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def ensure_image() -> bool:
    """Ensure the Docker image exists, building if necessary.

    Returns True if image is ready, False if build failed.
    """
    if _image_exists():
        return True
    logger.info("Docker image not found, building...")
    result = build_image()
    return result["success"]


def _build_docker_cmd(
    tmpdir: str,
    block_network: bool = True,
    memory: str = "512m",
    container_name: str = "",
    pids_limit: str = "256",
) -> List[str]:
    """Build a docker run command with standard security hardening."""
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{tmpdir}:/workspace",
        "-w", "/workspace",
        "--network", "none" if block_network else "bridge",
        "--memory", memory,
        "--memory-swap", memory,
        "--cpus", "2",
        "--pids-limit", pids_limit,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:rw,nosuid,size=64m",
        "--init",
    ]
    if container_name:
        cmd.extend(["--name", container_name])
    cmd.extend([
        IMAGE_NAME,
        "python", CONTAINER_RUNNER,
        "/workspace/_docker_config.json", "/workspace/_docker_result.json",
    ])
    return cmd


def _container_name_for_tmpdir(tmpdir: str) -> str:
    """Generate a deterministic container name from tmpdir path."""
    return f"benchmax_{os.path.basename(tmpdir)}"


def run_in_container(
    config: Dict[str, Any],
    tmpdir: str,
    timeout: float = 30.0,
    block_network: bool = True,
) -> List[Any]:
    """Run a code execution config inside a Docker container.

    Args:
        config: Dict with 'func' key (humaneval/bigcodebench/livecodebench/aider)
                plus function-specific args.
        tmpdir: Host directory to mount at /workspace inside container.
        timeout: Max seconds to wait for container.
        block_network: If True, disables container network access.

    Returns:
        List of result dicts (same format as multiprocessing.Manager.list()).
    """
    if not ensure_image():
        raise RuntimeError(
            "Docker image not available — build with: "
            "docker build -t benchmax-sandbox -f backend/docker/Dockerfile ."
        )

    config_path = os.path.join(tmpdir, "_docker_config.json")
    output_path = os.path.join(tmpdir, "_docker_result.json")

    with open(config_path, "w") as f:
        json.dump(config, f)

    name = _container_name_for_tmpdir(tmpdir)
    memory = "1g" if not block_network else "512m"
    cmd = _build_docker_cmd(tmpdir, block_network, memory, name)

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout + 10,
            encoding="utf-8", errors="replace",
        )
        elapsed = time.monotonic() - t0

        if os.path.exists(output_path):
            with open(output_path, "r") as f:
                result_list = json.load(f)
            logger.debug("Docker finished: elapsed=%.2fs status=%s", elapsed,
                        result_list[0] if isinstance(result_list[0], str) else "complex")
            return result_list

        stderr = result.stderr or ""
        if "timed out" in stderr.lower() or result.returncode == 124:
            return ["timed out"]

        if result.returncode != 0:
            return [f"failed: Docker exited with code {result.returncode}: {stderr[:300]}"]

        return ["failed: Docker produced no output"]

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - t0
        logger.warning("Docker container timed out after %.1fs", elapsed)
        _kill_container(name)
        return ["timed out"]
    except Exception as e:
        logger.warning("Docker execution failed: %s", e)
        return [f"failed: {e}"]


def run_aider_in_container(
    sample: Dict[str, Any],
    edited_code: str,
    tmpdir: str,
    timeout: float = 300.0,
) -> Dict[str, Any]:
    """Run Aider Polyglot test inside a Docker container.

    Aider needs network access (for npm/cargo/go module downloads)
    and writable workspace (for compilation artifacts).
    """
    config = {
        "func": "aider",
        "sample": sample,
        "edited_code": edited_code,
        "tmpdir": "/workspace",
    }

    if not ensure_image():
        raise RuntimeError("Docker image not available")

    config_path = os.path.join(tmpdir, "_docker_config.json")
    output_path = os.path.join(tmpdir, "_docker_result.json")

    with open(config_path, "w") as f:
        json.dump(config, f)

    name = _container_name_for_tmpdir(tmpdir)
    cmd = _build_docker_cmd(tmpdir, block_network=False, memory="1g", container_name=name)

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout + 30,
            encoding="utf-8", errors="replace",
        )
        elapsed = time.monotonic() - t0

        if os.path.exists(output_path):
            with open(output_path, "r") as f:
                result_data = json.load(f)
            logger.debug("Aider Docker finished: elapsed=%.2fs", elapsed)
            # Container may return a dict or a single-element list (backward compat)
            if isinstance(result_data, dict):
                return result_data
            if isinstance(result_data, list) and result_data and isinstance(result_data[0], dict):
                return result_data[0]
            return {"success": False, "stdout": "", "stderr": "",
                    "error": f"Unexpected result: {result_data}"}

        stderr = result.stderr or ""
        if result.returncode != 0:
            return {"success": False, "stdout": "", "stderr": stderr[:2000],
                    "error": f"Docker exited with code {result.returncode}"}

        return {"success": False, "stdout": "", "stderr": "",
                "error": "Docker produced no output"}

    except subprocess.TimeoutExpired:
        _kill_container(name)
        return {"success": False, "stdout": "", "stderr": "",
                "error": f"Aider Docker timed out ({timeout}s)"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": "", "error": str(e)}


def _kill_container(name: str):
    """Best-effort kill of a named container."""
    try:
        subprocess.run(
            ["docker", "kill", name],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def cleanup():
    """Remove the Docker image. Called on project cleanup."""
    try:
        subprocess.run(
            ["docker", "rmi", "-f", IMAGE_NAME],
            capture_output=True, timeout=30,
        )
    except Exception:
        pass
