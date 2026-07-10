import io
import logging
import os
import tarfile
import tempfile
import threading
import time
from pathlib import Path
from docker.errors import DockerException, ImageNotFound, APIError

logger = logging.getLogger(__name__)


class DockerExecutor:
    """Docker sandbox executor. Requires locally built BenchMax images — no fallback to registry."""

    # Local image names (no registry prefix — plain local tags)
    LOCAL_IMAGE_NAMES = [
        "benchmax-python",
        "benchmax-node",
        "benchmax-java",
        "benchmax-gcc",
        "benchmax-go",
        "benchmax-rust",
    ]

    # Benchmark → required local image mapping
    BENCHMARK_TO_LOCAL_IMAGE = {
        "humaneval": "benchmax-python",
        "bigcodebench": "benchmax-python",
        "bigcodebenchhard": "benchmax-python",
        "livebench": "benchmax-python",
        "javascript": "benchmax-node",
        "java":       "benchmax-java",
        "cpp":        "benchmax-gcc",
        "c++":        "benchmax-gcc",
        "go":         "benchmax-go",
        "rust":       "benchmax-rust",
    }

    def __init__(self):
        self.client = None
        self._local_images = {}  # image_name → tag (e.g. {"benchmax-python": "benchmax-python"})
        self.local_image_names = []
        self._reusable_containers = {}  # benchmark_name → container
        self._container_lock = threading.Lock()
        self._init_docker_client()

    def _init_docker_client(self):
        """Initialize Docker client and test connection."""
        try:
            self.client = __import__("docker").from_env()
            self.client.ping()
            logger.info("Docker client initialized successfully")
        except (DockerException, ImportError) as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None

    def is_available(self):
        """Check if Docker daemon is available."""
        if not self.client:
            self._init_docker_client()
        return self.client is not None

    def get_available_images(self):
        """Return dict of {image_name: bool} for all expected local images."""
        discovered = self._discover_local_images()
        return {name: name in discovered for name in self.LOCAL_IMAGE_NAMES}

    # ------------------------------------------------------------------
    # Local image detection & selection
    # ------------------------------------------------------------------

    def _discover_local_images(self):
        """Use client.images.list() to find locally built images.
        Returns dict of {image_name: tag} for images that exist."""
        if not self.client:
            return {}
        try:
            existing = set()
            for img in self.client.images.list():
                for tag in img.tags or []:
                    # Strip repo prefix (e.g. "benchmax-python" vs "localhost/benchmax-python")
                    base_tag = tag.rsplit(":", 1)[0] if ":" in tag else tag
                    existing.add(base_tag)
        except Exception as e:
            logger.warning(f"Could not list local images: {e}")

        result = {}
        for name in self.LOCAL_IMAGE_NAMES:
            if name in existing:
                result[name] = name
        return result

    def _local_image_exists(self, image_name):
        """Check if a local image with this name/tag exists."""
        try:
            self.client.images.get(image_name)
            return True
        except (ImageNotFound, Exception):
            return False

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------

    def _determine_command(self, image_tag, code):
        """Return the appropriate shell command for the given image.
        
        benchmax-python → python -c <code>
        benchmax-node   → node -e <code>
        benchmax-gcc    → not supported (compile-and-run requires temp files)
        """
        if "benchmax-python" in image_tag:
            return ["python", "-c", code]
        elif "benchmax-node" in image_tag:
            return ["node", "-e", code]
        else:
            raise RuntimeError(
                f"No execution strategy for image '{image_tag}'. "
                f"benchmax-python and benchmax-node are supported."
            )

    def _execute_with_new_container(self, code, timeout, image_tag):
        """Execute code inside a NEW container built from *image_tag* (old path)."""
        result = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": "",
            "image_used": image_tag,
            "execution_type": "local",
        }

        container = None
        try:
            cmd = self._determine_command(image_tag, code)
            container = self.client.containers.run(
                image=image_tag,
                command=cmd,
                network_disabled=True,
                mem_limit="256m",
                nano_cpus=1000000000,
                detach=True,
                stdout=True,
                stderr=True,
                remove=False,
            )

            exit_result = container.wait(timeout=timeout)
            exit_code = exit_result.get("StatusCode", -1) if isinstance(exit_result, dict) else exit_result

            logs_stdout = container.logs(stdout=True, stderr=False)
            logs_stderr = container.logs(stdout=False, stderr=True)

            stdout_str = logs_stdout.decode("utf-8", errors="replace") if logs_stdout else ""
            stderr_str = logs_stderr.decode("utf-8", errors="replace") if logs_stderr else ""

            if exit_code == 0:
                result["success"] = True
                result["stdout"] = stdout_str
                logger.info(f"Code executed successfully with {image_tag}")
            else:
                result["success"] = False
                result["stderr"] = stderr_str
                result["error"] = f"Execution failed with exit code {exit_code}: {stderr_str}"
                logger.error(f"Execution failed ({image_tag}): {stderr_str}")

        except Exception as e:
            result["success"] = False
            result["error"] = f"Container execution failed: {str(e)}"
            logger.error(f"Container error: {e}")
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

        return result

    def _execute_in_reusable_container(self, code, timeout, image_tag):
        """Execute code inside a REUSABLE container (created once, exec_run per sample)."""
        result = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": "",
            "image_used": image_tag,
            "execution_type": "reusable",
        }

        try:
            container = self._get_or_create_container(image_tag)
            exit_code, stdout_str, stderr_str = self._exec_in_container(container, code, image_tag, timeout)

            if exit_code == 0:
                result["success"] = True
                result["stdout"] = stdout_str
            else:
                result["success"] = False
                result["stderr"] = stderr_str
                result["error"] = f"Execution failed with exit code {exit_code}: {stderr_str}"
                logger.error(f"Execution failed (reusable {image_tag}): {stderr_str}")

        except Exception as e:
            result["success"] = False
            result["error"] = f"Reusable container execution failed: {str(e)}"
            logger.error(f"Reusable container error: {e}")

        return result

    def execute_python_code(self, code, timeout=5.0, benchmark_name=None):
        """Execute Python code in an isolated Docker sandbox.

        Requires locally built BenchMax images — no registry fallback.
        Raises RuntimeError if the required image is missing.
        """
        if not self.client:
            raise RuntimeError("Docker daemon is not available")

        # --- Resolve which local image this benchmark needs ---
        local_image = None
        if benchmark_name:
            normalized = benchmark_name.lower().replace(" ", "").replace("-", "")
            for key, img in self.BENCHMARK_TO_LOCAL_IMAGE.items():
                if key in normalized or normalized in key:
                    local_image = img
                    break

        # --- Fallback: guess from available local images ---
        if not local_image:
            discovered = self._discover_local_images()
            if discovered:
                local_image = discovered.get(self.LOCAL_IMAGE_NAMES[0])
            logger.info(f"No benchmark mapping for '{benchmark_name}', falling back to '{local_image}'")

        # --- Check that the required image exists locally ---
        if not local_image or not self._local_image_exists(local_image):
            raise RuntimeError(
                f"Required BenchMax image '{local_image}' is not found locally. "
                f"Build it first with: scripts/build_docker_images.py\n"
                f"\nOr click '🏗️ Build Local Images' in the UI."
            )

        logger.info(f"Using local image: {local_image} for benchmark '{benchmark_name}'")
        if benchmark_name:
            return self._execute_in_reusable_container(code, timeout, local_image)
        return self._execute_with_new_container(code, timeout, local_image)

    # ------------------------------------------------------------------
    # Container reuse (eliminates per-sample container creation overhead)
    # ------------------------------------------------------------------

    def _get_or_create_container(self, image_tag, network_enabled=False):
        """Get a reusable container for the given image, or create one."""
        key = f"{image_tag}:net={network_enabled}"
        with self._container_lock:
            if key in self._reusable_containers:
                try:
                    self._reusable_containers[key].reload()
                    if self._reusable_containers[key].status == "running":
                        return self._reusable_containers[key]
                except APIError:
                    pass
                self._reusable_containers.pop(key, None)

        container = self.client.containers.run(
            image=image_tag,
            command=["sleep", "infinity"],
            network_disabled=not network_enabled,
            mem_limit="256m",
            nano_cpus=1000000000,
            detach=True,
            remove=False,
        )
        with self._container_lock:
            self._reusable_containers[key] = container
        return container

    def _exec_run_with_timeout(self, container, cmd, timeout, workdir=None, environment=None):
        """Run exec_run in a worker thread so we can enforce a wall-clock timeout.

        docker-py's Container.exec_run() does NOT accept a `timeout` keyword, so calling
        it with one raises TypeError (which previously failed every sample silently).
        This wrapper restores a timeout safety net without breaking the call signature.
        """
        holder = {}

        def _worker():
            try:
                exec_result = container.exec_run(cmd=cmd, stdout=True, stderr=True, workdir=workdir, environment=environment)
                out = exec_result.output
                holder["exit_code"] = exec_result.exit_code
                holder["output"] = out.decode("utf-8", errors="replace") if isinstance(out, bytes) else str(out)
            except Exception as e:
                holder["error"] = f"exec_run failed: {str(e)}"

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            return -1, "", "", f"exec_run timed out after {timeout}s"
        if "error" in holder:
            return -1, "", "", holder["error"]
        return holder["exit_code"], holder.get("output", ""), holder.get("stderr", ""), ""

    def _exec_in_container(self, container, code, image_tag, timeout):
        """Execute code inside a running container via exec_run."""
        cmd = self._determine_command(image_tag, code)
        exit_code, combined, stderr_str, _ = self._exec_run_with_timeout(container, cmd, timeout)
        return exit_code, combined, stderr_str

    def cleanup(self, benchmark_name=None):
        """Remove reusable container(s). Call when a benchmark finishes."""
        with self._container_lock:
            if benchmark_name:
                resolved_name = self._resolve_image_key(benchmark_name)
                if resolved_name in self._reusable_containers:
                    try:
                        self._reusable_containers[resolved_name].remove(force=True)
                    except Exception:
                        pass
                    del self._reusable_containers[resolved_name]
                    logger.info(f"Cleaned up container for {benchmark_name}")
            else:
                for name, container in list(self._reusable_containers.items()):
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass
                self._reusable_containers.clear()
                logger.info("Cleaned up all reusable containers")

    def _resolve_image_key(self, benchmark_name):
        """Map a benchmark name to its image tag."""
        if not benchmark_name:
            return None
        normalized = benchmark_name.lower().replace(" ", "").replace("-", "")
        for key, img in self.BENCHMARK_TO_LOCAL_IMAGE.items():
            if key in normalized or normalized in key:
                return img
        return self.LOCAL_IMAGE_NAMES[0] if self.LOCAL_IMAGE_NAMES else None

    def _tar_workspace(self, workspace_dir: str) -> bytes:
        """Create a tar archive of a workspace directory for upload to a container."""
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            base = Path(workspace_dir)
            for entry in sorted(base.rglob('*')):
                if entry.is_dir():
                    continue
                rel = entry.relative_to(base)
                info = tarfile.TarInfo(name=str(rel.as_posix()))
                info.size = entry.stat().st_size
                info.mtime = int(entry.stat().st_mtime)
                with open(entry, 'rb') as f:
                    tar.addfile(info, f)
        tar_stream.seek(0)
        return tar_stream.read()

    def execute_command(self, command, image_tag, workspace_dir=None, timeout=120, network_enabled=False, env=None):
        """Execute an arbitrary command inside a reusable container.

        Args:
            command: List of command + args (e.g. ["bash", "-c", "..."] or ["go", "test", "./..."])
            image_tag: BenchMax image tag (e.g. "benchmax-node")
            workspace_dir: Optional host path to upload as /workspace/
            timeout: Command timeout in seconds
            network_enabled: Whether to enable networking (default: False)

        Returns:
            dict with keys: success, stdout, stderr, error
        """
        result = {"success": False, "stdout": "", "stderr": "", "error": ""}

        if not self.client:
            result["error"] = "Docker daemon is not available"
            return result

        if not image_tag:
            result["error"] = "No image tag provided"
            return result

        if not self._local_image_exists(image_tag):
            result["error"] = (
                f"Required BenchMax image '{image_tag}' is not found locally. "
                f"Build it first with: scripts/build_docker_images.py"
            )
            return result

        try:
            container = self._get_or_create_container(image_tag, network_enabled=network_enabled)

            if workspace_dir and os.path.isdir(workspace_dir):
                try:
                    tar_data = self._tar_workspace(workspace_dir)
                    container.put_archive("/workspace", tar_data)
                except Exception as e:
                    logger.warning(f"Failed to upload workspace to container: {e}")

            if not isinstance(command, list):
                command = ["bash", "-c", str(command)]

            exit_code, combined, stderr_str, error_str = self._exec_run_with_timeout(container, command, timeout, workdir="/workspace", environment=env)

            if error_str:
                result["error"] = error_str
                return result

            result["success"] = (exit_code == 0)
            result["stdout"] = combined[:5000] if combined else ""
            result["stderr"] = stderr_str[:2000] if stderr_str else ""
            if not result["success"]:
                result["error"] = f"Command failed with exit code {exit_code}: {combined[:500]}"
            else:
                logger.info(f"Command executed successfully in {image_tag}")

        except Exception as e:
            result["error"] = f"Command execution failed: {str(e)}"
            logger.error(f"Command error: {e}")

        return result

    # ------------------------------------------------------------------
    # Public helpers (kept for backward compat)
    # ------------------------------------------------------------------

    def _get_preferred_local_image(self, benchmark_name):
        """Determine which local image to use based on benchmark name."""
        if not benchmark_name:
            return None

        normalized = benchmark_name.lower().replace(" ", "").replace("-", "")

        for key, image in self.BENCHMARK_TO_LOCAL_IMAGE.items():
            if key in normalized:
                return f"{image}:latest"

        # Default to first available local image
        discovered = self._discover_local_images()
        if not discovered:
            return None
        return f"{discovered.get(self.LOCAL_IMAGE_NAMES[0], '')}:latest" or None
