"""LiveBench partial-Docker behavior: coding skips without Docker, warns without blocking.

- Skip happens BEFORE generation (no LLM time/tokens wasted).
- Probe result cached per benchmark instance (one docker probe per run).
- Readiness reports severity "warning" for LiveBench (never blocks Start);
  full-Docker benchmarks stay "blocking".
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


def _mock_gen(text):
    return {
        "raw_response": text, "thinking_content": "", "answer_content": text,
        "elapsed_time": 0.5, "tps": 10.0, "ttft": 0.1,
        "thinking_tokens": 0, "response_tokens": 5, "prompt_tokens": 50,
    }


def _coding_sample():
    return {
        "task_id": "lb-code/0",
        "category": "coding",
        "question": "Write a function solution(x) that returns x*2.",
        "test": "def check(solution):\n    assert solution(2) == 4",
        "entry_point": "solution",
    }


def _mcq_sample():
    return {
        "task_id": "lb-mcq/0",
        "category": "mcq",
        "question": "What is 2+2?",
        "options": ["3", "4", "5", "6"],
        "answer": "B",
    }


def _bench():
    from backend.benchmarks.livebench import LiveBenchBenchmark
    client = MagicMock()
    client.generate_completion = AsyncMock(return_value=_mock_gen("B"))
    return LiveBenchBenchmark(MagicMock(), client, quick_test=True)


class TestCodingSkip:
    def test_skipped_before_generation(self):
        bench = _bench()
        bench._docker_usable_cache = False  # Docker down
        out = asyncio.run(bench.evaluate_sample(
            _coding_sample(), {"temperature": 0.0}, "m"))
        assert out["correct"] is False
        assert "Skipped" in (out["error_message"] or "")
        assert "Docker" in (out["error_message"] or "")
        bench.client.generate_completion.assert_not_awaited()
        import json
        sd = out["scoring_details"] if isinstance(out["scoring_details"], dict) \
            else json.loads(out["scoring_details"])
        assert sd["category"] == "coding"
        assert sd["skipped"] is True

    def test_proceeds_when_docker_up(self):
        bench = _bench()
        bench._docker_usable_cache = True
        bench.client.generate_completion = AsyncMock(
            return_value=_mock_gen("```python\ndef solution(x):\n    return x*2\n```"))
        # Imported lazily inside evaluate_sample — patch at the source.
        with patch("backend.sandbox.safe_executor.check_correctness_humaneval",
                   return_value={"passed": True, "result": "passed"}) as checker:
            out = asyncio.run(bench.evaluate_sample(
                _coding_sample(), {"temperature": 0.0}, "m"))
        assert checker.called
        assert out["correct"] is True
        bench.client.generate_completion.assert_awaited()

    def test_probe_cached_per_instance(self):
        bench = _bench()
        calls = {"daemon": 0, "image": 0}

        def _daemon():
            calls["daemon"] += 1
            return True

        def _image():
            calls["image"] += 1
            return True

        with patch("backend.sandbox.docker_executor._docker_available", side_effect=_daemon), \
             patch("backend.sandbox.docker_executor._image_exists", side_effect=_image):
            assert bench._docker_usable() is True
            assert bench._docker_usable() is True
        assert calls == {"daemon": 1, "image": 1}

    def test_probe_failure_means_unusable(self):
        bench = _bench()
        with patch("backend.sandbox.docker_executor._docker_available",
                   side_effect=RuntimeError("no docker")):
            assert bench._docker_usable() is False


class TestNonCodingUnaffected:
    def test_mcq_runs_without_docker(self):
        bench = _bench()
        bench._docker_usable_cache = False
        out = asyncio.run(bench.evaluate_sample(
            _mcq_sample(), {"temperature": 0.0}, "m"))
        assert out["correct"] is True
        bench.client.generate_completion.assert_awaited()


class TestReadinessSeverity:
    def _docker_down(self):
        return (patch("backend.ops.datasets._docker_daemon_running", return_value=False),
                patch("backend.sandbox.docker_executor._image_exists", return_value=False))

    def test_livebench_warns_not_blocks(self):
        from backend.operations import check_benchmark_readiness
        d, i = self._docker_down()
        with d, i:
            issues = check_benchmark_readiness("LiveBench", quick_test=True)
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"
        assert issues[0]["kind"] == "runtime"
        assert issues[0]["action"] == "download_runtime"
        assert "skipped" in issues[0]["message"]

    def test_livebench_image_missing_warns(self):
        from backend.operations import check_benchmark_readiness
        with patch("backend.ops.datasets._docker_daemon_running", return_value=True), \
             patch("backend.sandbox.docker_executor._image_exists", return_value=False):
            issues = check_benchmark_readiness("LiveBench", quick_test=True)
        assert len(issues) == 1 and issues[0]["severity"] == "warning"

    def test_livebench_ready_when_docker_up(self):
        from backend.operations import check_benchmark_readiness
        with patch("backend.ops.datasets._docker_daemon_running", return_value=True), \
             patch("backend.sandbox.docker_executor._image_exists", return_value=True):
            assert check_benchmark_readiness("LiveBench", quick_test=True) == []

    def test_full_docker_benchmark_still_blocking(self):
        from backend.operations import check_benchmark_readiness
        d, i = self._docker_down()
        with d, i:
            issues = check_benchmark_readiness("HumanEval", quick_test=True)
        assert len(issues) == 1
        assert issues[0]["severity"] == "blocking"


class TestRunCheckEndpoint:
    def test_warnings_do_not_block(self):
        from httpx import AsyncClient, ASGITransport
        from backend.main import app
        import asyncio as _aio

        async def _go():
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport,
                                   base_url="http://test") as c:
                with patch("backend.ops.datasets._docker_daemon_running",
                           return_value=False), \
                     patch("backend.sandbox.docker_executor._image_exists",
                           return_value=False):
                    return await c.post("/api/run/check", json={
                        "benchmarks": ["LiveBench"], "quick_test": True})
        resp = _aio.run(_go())
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["issues"] == []
        assert len(body["warnings"]) == 1
        assert body["warnings"][0]["severity"] == "warning"
