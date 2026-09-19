"""Engine-wedge detection: container timeouts must name a wedged daemon.

`docker info`/`docker ps` can succeed while container *start* hangs forever
(wedged Docker Desktop backend). When a benchmark container times out,
_run probes the engine with a trivial `docker run` and appends the diagnosis
so users see "engine cannot start containers" instead of a bare timeout.
All probing is mocked — no Docker needed.
"""

import subprocess
from unittest.mock import MagicMock, patch

import backend.sandbox.docker_executor as dex


def _reset_probe_cache():
    dex._engine_probe_cache["at"] = 0.0
    dex._engine_probe_cache["ok"] = True


def _ok_run(*args, **kwargs):
    m = MagicMock()
    m.returncode = 0
    m.stdout = "ok\n"
    return m


class TestEngineProbe:
    def test_healthy_engine(self):
        _reset_probe_cache()
        with patch.object(dex.subprocess, "run", side_effect=_ok_run):
            assert dex._engine_can_start_containers() is True
            assert dex._engine_wedge_suffix() == ""

    def test_wedged_engine_reports(self):
        _reset_probe_cache()
        with patch.object(
            dex.subprocess, "run",
            side_effect=subprocess.TimeoutExpired("docker", 30),
        ):
            assert dex._engine_can_start_containers() is False
            suffix = dex._engine_wedge_suffix()
            assert "cannot start containers" in suffix
            assert "docker run --rm benchmax-sandbox echo ok" in suffix

    def test_probe_result_cached(self):
        _reset_probe_cache()
        with patch.object(
            dex.subprocess, "run", side_effect=_ok_run
        ) as mock_run:
            assert dex._engine_can_start_containers() is True
            assert dex._engine_can_start_containers() is True
            assert mock_run.call_count == 1


class TestTimeoutErrors:
    def test_aider_timeout_names_wedge(self):
        _reset_probe_cache()
        with patch.object(dex, "ensure_image", return_value=True), \
             patch.object(dex, "_kill_container"), \
             patch.object(
                 dex.subprocess, "run",
                 side_effect=subprocess.TimeoutExpired("docker", 300),
             ):
            result = dex.run_aider_in_container(
                {"language": "python"}, "code", __import__("tempfile").mkdtemp(),
                timeout=120,
            )
            assert result["success"] is False
            assert "timed out" in result["error"]
            assert "cannot start containers" in result["error"]

    def test_aider_timeout_bare_when_healthy(self):
        _reset_probe_cache()
        calls = {"n": 0}

        def _run(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise subprocess.TimeoutExpired("docker", 300)
            return _ok_run()

        with patch.object(dex, "ensure_image", return_value=True), \
             patch.object(dex, "_kill_container"), \
             patch.object(dex.subprocess, "run", side_effect=_run):
            result = dex.run_aider_in_container(
                {"language": "python"}, "code", __import__("tempfile").mkdtemp(),
                timeout=120,
            )
            assert result["error"] == "Aider Docker timed out (120s)"

    def test_generic_timeout_names_wedge(self, tmp_path):
        _reset_probe_cache()
        with patch.object(dex, "ensure_image", return_value=True), \
             patch.object(dex, "_kill_container"), \
             patch.object(
                 dex.subprocess, "run",
                 side_effect=subprocess.TimeoutExpired("docker", 30),
             ):
            result = dex.run_in_container(
                {"func": "humaneval"}, str(tmp_path), timeout=30,
            )
            assert result[0].startswith("timed out")
            assert "cannot start containers" in result[0]
