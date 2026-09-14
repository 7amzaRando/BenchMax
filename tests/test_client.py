"""Tests for backend/lm_studio/client.py — repetition detection, parsing, client lifecycle.

All network-free: repetition and parsing are pure in-memory; HTTP paths use
respx-style monkeypatched _get_client fakes. No LM Studio required.
"""
import asyncio
import json as _json
from unittest.mock import MagicMock

from backend.lm_studio.client import LMStudioClient


def _client_with_buffer(text: str) -> LMStudioClient:
    c = LMStudioClient(base_url="http://127.0.0.1:1234/v1")
    c._rep_buffer = text
    c._rep_consecutive_count = 0
    return c


class TestInit:
    def test_strips_trailing_slash(self):
        c = LMStudioClient(base_url="http://127.0.0.1:1234/v1/")
        assert c.base_url == "http://127.0.0.1:1234/v1"

    def test_api_key_header(self):
        c = LMStudioClient(base_url="http://x/v1", api_key="k123")
        assert c._headers["Authorization"] == "Bearer k123"

    def test_no_api_key_no_auth_header(self):
        c = LMStudioClient(base_url="http://x/v1")
        assert "Authorization" not in c._headers


class TestRepetition:
    def test_short_buffer_never_flags(self):
        c = _client_with_buffer("abc " * 50)  # 200 chars < 400 minimum
        assert c._check_repetition() is False
        assert c._rep_consecutive_count == 0

    def test_verbatim_loop_confirms_after_three(self):
        tail = "x" * 200
        buf = ("y" * 200 + tail) + tail  # tail appears earlier in body
        c = _client_with_buffer(buf + " " * 100)  # ensure len >= 400
        # Rebuild so tail-in-body holds: last 200 chars must appear earlier
        frag = "LOOP-FRAGMENT-" * 14  # 210 chars
        frag = frag[:200]
        c._rep_buffer = ("prefix " + frag + " middle ") * 4 + frag
        assert c._check_repetition() is False  # 1st event
        assert c._check_repetition() is False  # 2nd event
        assert c._check_repetition() is True  # 3rd consecutive confirms

    def test_cooldown_resets_on_clean_chunk(self):
        frag = ("Q" * 200)
        c = _client_with_buffer(("p " + frag + " m ") * 4 + frag)
        assert c._check_repetition() is False
        assert c._check_repetition() is False
        # Genuinely varied buffer (unique numbered sentences) breaks the streak.
        # NOTE: must not repeat a 150+ char fragment 3x, or strategy C fires.
        c._rep_buffer = " ".join(
            f"Sentence {i}: the river bends past willow {i * 7} under cloud {i * 13}."
            for i in range(40))
        assert c._check_repetition() is False
        assert c._rep_consecutive_count == 0

    def test_normal_prose_does_not_flag(self):
        prose = ("The quick brown fox jumps over the lazy dog. " * 40)[:1200]
        c = _client_with_buffer(prose)
        assert c._check_repetition() is False

    def test_none_response_guard_documented(self):
        # _check_repetition operates on str buffer; empty buffer is the
        # degenerate case and must never flag.
        c = _client_with_buffer("")
        assert c._check_repetition() is False


class TestReasoningParsing:
    def test_reasoning_content_field_split(self):
        c = LMStudioClient()
        thinking, answer = c._parse_reasoning_and_answer(
            "ignored",
            {"choices": [{"message": {"reasoning_content": "plan here",
                                      "content": "Final answer"}}]})
        assert thinking == "plan here"
        assert answer == "Final answer"

    def test_plain_text_is_all_answer(self):
        c = LMStudioClient()
        thinking, answer = c._parse_reasoning_and_answer("Just the answer")
        assert thinking == ""
        assert answer == "Just the answer"


class TestClientLoopSwitch:
    def test_get_client_recreates_on_loop_switch(self):
        async def _use():
            c = LMStudioClient()
            c._get_client()
            await c.aclose()
            return c
        c = asyncio.run(_use())

        async def _reuse_same_client():
            # Same client object on a FRESH loop must not reuse the dead pool
            second = c._get_client()
            await c.aclose()
            return second
        second = asyncio.run(_reuse_same_client())
        assert second is not None


# ── generate_completion streaming (fake HTTP, no network) ──────────


def _sse_data(obj) -> str:
    return "data: " + _json.dumps(obj)


def _content_chunk(text, reasoning=None):
    delta = {}
    if text is not None:
        delta["content"] = text
    if reasoning is not None:
        delta["reasoning_content"] = reasoning
    return _sse_data({"choices": [{"delta": delta}]})


class _FakeStreamResp:
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b"fake error body"

    async def aclose(self):
        self.closed = True


class _FakeHTTP:
    """Stands in for httpx.AsyncClient: records payloads, replays SSE lines."""
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code
        self.stream_payloads = []
        self.post_payloads = []

    def stream(self, method, url, json=None, timeout=None):
        self.stream_payloads.append({"method": method, "url": url, "json": json})
        return _FakeStreamResp(self._lines, self.status_code)

    async def post(self, url, json=None, timeout=None):
        self.post_payloads.append({"url": url, "json": json})
        resp = MagicMock()
        resp.status_code = 200
        return resp


def _run(coro):
    return asyncio.run(coro)


class TestGenerateCompletion:
    def _client(self, lines, status=200):
        from unittest.mock import MagicMock
        c = LMStudioClient(base_url="http://127.0.0.1:1234/v1")
        fake = _FakeHTTP(lines, status)
        c._get_client = MagicMock(return_value=fake)
        return c, fake

    def test_content_assembles_answer(self):
        lines = [_content_chunk("Hello "), _content_chunk("world"),
                 _sse_data({"choices": [], "usage": {"prompt_tokens": 8, "completion_tokens": 4}}),
                 "data: [DONE]"]
        c, _ = self._client(lines)
        out = _run(c.generate_completion("Say hi", model_name="m"))
        assert out["answer_content"] == "Hello world"
        assert out["thinking_content"] == ""
        assert out["prompt_tokens"] == 8
        assert out["response_tokens"] == 4
        assert out["elapsed_time"] >= 0.0

    def test_reasoning_content_split(self):
        lines = [_content_chunk(None, reasoning="plan "),
                 _content_chunk("Final"),
                 "data: [DONE]"]
        c, _ = self._client(lines)
        out = _run(c.generate_completion("q", model_name="m"))
        assert out["thinking_content"] == "plan "
        assert out["answer_content"] == "Final"
        assert out["raw_response"].startswith("<think>")

    def test_max_completion_tokens_alias_wins(self):
        c, fake = self._client(["data: [DONE]"])
        _run(c.generate_completion("q", model_name="m",
                                   max_tokens=100, max_completion_tokens=77))
        assert fake.stream_payloads[0]["json"]["max_tokens"] == 77

    def test_temperature_none_omitted(self):
        c, fake = self._client(["data: [DONE]"])
        _run(c.generate_completion("q", model_name="m", temperature=None))
        assert "temperature" not in fake.stream_payloads[0]["json"]

    def test_stop_tokens_and_system_prompt(self):
        c, fake = self._client(["data: [DONE]"])
        _run(c.generate_completion("q", system_prompt="sys", stop_tokens=["STOP"],
                                   model_name="m"))
        payload = fake.stream_payloads[0]["json"]
        assert payload["stop"] == ["STOP"]
        assert payload["messages"][0] == {"role": "system", "content": "sys"}
        assert payload["messages"][-1] == {"role": "user", "content": "q"}

    def test_images_become_multipart(self):
        c, fake = self._client(["data: [DONE]"])
        _run(c.generate_completion("look", model_name="m", images=["QUJD"]))
        content = fake.stream_payloads[0]["json"]["messages"][-1]["content"]
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "look"}
        assert content[1]["image_url"]["url"].endswith("QUJD")

    def test_non_200_raises(self):
        import pytest as _pt
        c, _ = self._client([], status=500)
        with _pt.raises(RuntimeError, match="status 500"):
            _run(c.generate_completion("q", model_name="m"))

    def test_no_model_raises(self):
        import pytest as _pt
        from unittest.mock import AsyncMock
        c = LMStudioClient()
        c.get_active_model_name = AsyncMock(return_value=None)
        with _pt.raises(ValueError, match="No model is loaded"):
            _run(c.generate_completion("q"))

    def test_rep_disabled_never_flags(self):
        frag = "Z" * 200
        lines = [_content_chunk(frag) for _ in range(8)] + ["data: [DONE]"]
        c, _ = self._client(lines)
        c._rep_disabled = True
        c._rep_check_interval = 1
        out = _run(c.generate_completion("q", model_name="m"))
        assert c._repetition_detected is False
        assert out["answer_content"] == frag * 8

    def test_rep_loop_aborts_stream(self):
        frag = "W" * 200
        lines = [_content_chunk(frag) for _ in range(10)] + ["data: [DONE]"]
        c, _fake = self._client(lines)
        c._rep_check_interval = 1
        _run(c.generate_completion("q", model_name="m"))
        assert c._repetition_detected is True

    def test_chat_completion_forwards_messages(self):
        c, fake = self._client([_content_chunk("hi"), "data: [DONE]"])
        out = _run(c.generate_chat_completion(
            [{"role": "user", "content": "hello"}], model_name="m"))
        assert fake.stream_payloads[0]["json"]["messages"] == [
            {"role": "user", "content": "hello"}]
        assert out["answer_content"] == "hi"
