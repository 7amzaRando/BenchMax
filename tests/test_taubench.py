"""Tests for the Tau3-Airline benchmark (multi-turn customer-service tool use).

Gold-replay tests require the vendored data files (scripts/fetch_taubench_airline.py)
and are skipped when they are absent. Tool/grading unit tests run offline.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

DATA_DIR = Path(__file__).parents[1] / "data"
DATA_PRESENT = (DATA_DIR / "taubench_airline_full.json").exists()
needs_data = pytest.mark.skipif(not DATA_PRESENT, reason="Tau3-Airline data not installed")


def _run_async(coro):
    return asyncio.run(coro)


def _mock_gen(response="###STOP###", tps=50.0, ttft=0.3):
    return {
        "model_name": "test-model",
        "raw_response": response,
        "thinking_content": "",
        "answer_content": response,
        "elapsed_time": 1.5,
        "ttft": ttft,
        "tps": tps,
        "prompt_tokens": 100,
        "response_tokens": 20,
        "thinking_tokens": 0,
        "answer_tokens": 20,
        "stream_timed_out": False,
    }


def _bench(**kwargs):
    from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
    db = MagicMock()
    client = MagicMock()
    client.generate_chat_completion = AsyncMock(side_effect=kwargs.get("side_effect"))
    client._rep_disabled = False
    client._repetition_detected = False
    bench = Tau3AirlineBenchmark(db, client, quick_test=True)
    # Avoid real context-limit queries against LM Studio.
    bench._get_model_context_limit = AsyncMock(return_value=32768)
    return bench


def _sample(**overrides):
    s = {
        "task_id": "tau3-airline/test",
        "user_scenario": {
            "persona": None,
            "instructions": {
                "domain": "airline",
                "reason_for_call": "I want to check my reservation.",
                "known_info": "You are Test User.",
                "unknown_info": None,
                "task_instructions": "Ask about your reservation, then stop.",
            },
        },
        "reference_actions": [],
        "communicate_info": [],
        "max_turns": 5,
        "max_wall_clock_sec": 120,
        "category": "airline",
    }
    s.update(overrides)
    return s


# ── Tool environment ────────────────────────────────────────────────

class TestAirlineTools:
    def test_unknown_user_error_verbatim(self):
        from backend.benchmarks.taubench_airline import _AirlineEnv
        env = _AirlineEnv({"users": {}, "reservations": {}, "flights": {}})
        with pytest.raises(ValueError, match=r"User ghost_1 not found"):
            env.call("get_user_details", {"user_id": "ghost_1"})

    def test_unknown_reservation_error_verbatim(self):
        from backend.benchmarks.taubench_airline import _AirlineEnv
        env = _AirlineEnv({"users": {}, "reservations": {}, "flights": {}})
        with pytest.raises(ValueError, match=r"Reservation NOPE12 not found"):
            env.call("cancel_reservation", {"reservation_id": "NOPE12"})

    def test_unknown_tool(self):
        from backend.benchmarks.taubench_airline import _AirlineEnv
        env = _AirlineEnv({"users": {}, "reservations": {}, "flights": {}})
        with pytest.raises(ValueError, match="Unknown tool"):
            env.call("fly_to_the_moon", {})

    def test_calculate(self):
        from backend.benchmarks.taubench_airline import _AirlineEnv
        env = _AirlineEnv({"users": {}, "reservations": {}, "flights": {}})
        assert env.call("calculate", {"expression": "2 + 3 * 4"}) == "14.0"
        with pytest.raises(ValueError, match="Invalid characters"):
            env.call("calculate", {"expression": "__import__('os')"})

    def test_cancel_adds_status_and_refunds(self):
        from backend.benchmarks.taubench_airline import _AirlineEnv
        res = {"reservation_id": "ABC123", "user_id": "u1",
               "payment_history": [{"payment_id": "cc_1", "amount": 500}],
               "passengers": []}
        env = _AirlineEnv({"users": {}, "reservations": {"ABC123": res}, "flights": {}})
        out = env.call("cancel_reservation", {"reservation_id": "ABC123"})
        assert out["status"] == "cancelled"
        assert {"payment_id": "cc_1", "amount": -500} in out["payment_history"]

    def test_list_airports_count(self):
        from backend.benchmarks.taubench_airline import _AirlineEnv
        env = _AirlineEnv({"users": {}, "reservations": {}, "flights": {}})
        airports = env.call("list_all_airports", {})
        assert len(airports) == 20

    def test_transfer(self):
        from backend.benchmarks.taubench_airline import _AirlineEnv
        env = _AirlineEnv({"users": {}, "reservations": {}, "flights": {}})
        assert env.call("transfer_to_human_agents", {"summary": "x"}) == "Transfer successful"


# ── Grading semantics ───────────────────────────────────────────────

class TestCommunicateMatch:
    def test_empty_auto_pass(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        assert Tau3AirlineBenchmark._communicate_match(_sample(), [])["match"] is True

    def test_substring_case_insensitive(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        s = _sample(communicate_info=["reservation EHGLP3"])
        conv = [{"role": "assistant", "content": "Your Reservation ehglp3 is cancelled."}]
        assert Tau3AirlineBenchmark._communicate_match(s, conv)["match"] is True

    def test_comma_stripped_from_message_side(self):
        """Upstream: info in message.lower().replace(',', '') — info keeps commas."""
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        s = _sample(communicate_info=["4"])
        conv = [{"role": "assistant", "content": "There are 1,4 seats."}]
        # "1,4" -> "14" contains "4"
        assert Tau3AirlineBenchmark._communicate_match(s, conv)["match"] is True

    def test_missing_reported(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        s = _sample(communicate_info=["refund of $200"])
        conv = [{"role": "assistant", "content": "Done."}]
        res = Tau3AirlineBenchmark._communicate_match(s, conv)
        assert res["match"] is False
        assert res["missing"] == ["refund of $200"]

    def test_user_messages_not_scanned(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        s = _sample(communicate_info=["secret"])
        conv = [{"role": "user", "content": "the secret is out"}]
        assert Tau3AirlineBenchmark._communicate_match(s, conv)["match"] is False


# ── Gold replay (needs data) ────────────────────────────────────────

@pytest.mark.timeout(300)
class TestGoldReplay:
    @needs_data
    def test_all_tasks_replay_deterministically(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        bench = Tau3AirlineBenchmark(MagicMock(), MagicMock(), quick_test=False)
        ds = bench.load_dataset()
        assert len(ds) == 50
        for s in ds:
            h1 = bench.replay_reference(s)["hash"]
            h2 = bench.replay_reference(s)["hash"]
            assert h1 == h2, s["task_id"]

    @needs_data
    def test_all_tasks_replay_without_errors(self):
        """Every reference trajectory must replay cleanly — validates the DB port."""
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        bench = Tau3AirlineBenchmark(MagicMock(), MagicMock(), quick_test=False)
        bad = {}
        for s in bench.load_dataset():
            errors = bench.replay_reference(s)["errors"]
            if errors:
                bad[s["task_id"]] = errors
        assert not bad, f"gold replay errors: {json.dumps(bad, indent=1)[:2000]}"

    @needs_data
    def test_score_agrees_on_reference_trajectory(self):
        """Predicted DB == gold DB + communicated strings -> correct (upstream semantics)."""
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        bench = Tau3AirlineBenchmark(MagicMock(), MagicMock(), quick_test=False)
        ds = bench.load_dataset()
        checked = 0
        for s in ds:
            gold = bench.replay_reference(s)
            bench._live_db[s["task_id"]] = gold["db"]
            conv = [{"role": "assistant",
                     "content": " ".join(s.get("communicate_info") or ["done"])}]
            res = bench.score(s, conv, conv[0]["content"])
            assert res["correct"] is True, s["task_id"]
            assert res["details"]["db_match"] is True
            bench._live_db.pop(s["task_id"], None)
            checked += 1
        assert checked == 50

    @needs_data
    def test_score_fails_on_mutated_db(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        bench = Tau3AirlineBenchmark(MagicMock(), MagicMock(), quick_test=False)
        s = bench.load_dataset()[0]
        gold = bench.replay_reference(s)
        db = gold["db"]
        rid = next(iter(db["reservations"]))
        db["reservations"][rid + "_tampered"] = {"tampered": True}
        bench._live_db[s["task_id"]] = db
        res = bench.score(s, [{"role": "assistant", "content": "done"}], "done")
        assert res["correct"] is False
        assert res["details"]["db_match"] is False
        bench._live_db.pop(s["task_id"], None)


# ── Conversation loop (mocked model) ────────────────────────────────

def _router(agent_text, user_text):
    """Route generate_chat_completion to agent or user script by system prompt."""
    async def _route(messages, **kwargs):
        system = messages[0].get("content", "") if messages else ""
        if "<scenario>" in system:
            return _mock_gen(user_text)
        return _mock_gen(agent_text)
    return _route


class TestConversationLoop:
    def test_user_stop_flow_scores_db_match(self):
        bench = _bench(side_effect=_router(
            "Let me look that up for you.",
            "Thanks, that answers it. ###STOP###"))
        result = _run_async(bench.evaluate_sample(
            _sample(), {"temperature": 0.0, "max_completion_tokens": 512}, "test"))
        # No reference actions + no mutations -> DB matches gold.
        assert result["correct"] is True
        details = result["scoring_details"]
        assert details["db_match"] is True
        assert details["termination"] == "user_stop"
        roles = [t["role"] for t in details["turns"]]
        assert "user" in roles and "assistant" in roles

    def test_agent_tool_call_executes_and_scores(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        bench = Tau3AirlineBenchmark(MagicMock(), MagicMock(), quick_test=True)
        bench._get_model_context_limit = AsyncMock(return_value=32768)
        bench._load_shared()
        import copy
        user_id = next(iter(Tau3AirlineBenchmark._base_db["users"]))
        agent_text = (
            '{"name": "get_user_details", "arguments": {"user_id": "%s"}}\n###STOP###'
            % user_id)
        bench.client.generate_chat_completion = AsyncMock(
            side_effect=_router(agent_text, "OK, please proceed."))
        result = _run_async(bench.evaluate_sample(
            _sample(), {"temperature": 0.0, "max_completion_tokens": 512}, "test"))
        details = result["scoring_details"]
        tool_turns = [t for t in details["turns"] if t["role"] == "tool"]
        assert tool_turns, "expected tool result turns"
        assert "not found" not in tool_turns[0]["content"]
        assert result["correct"] is True  # read-only -> DB unchanged

    def test_tool_error_loop_aborts(self):
        bench = _bench(side_effect=_router(
            '```tool\n{"name": "get_user_details", "arguments": {"user_id": "nobody"}}\n```',
            "Keep trying."))
        result = _run_async(bench.evaluate_sample(
            # Unmet communicate_info so the aborted run scores incorrect
            # (an untouched DB alone would legitimately match gold).
            _sample(max_turns=30, communicate_info=["refund confirmation code XYZ"]),
            {"temperature": 0.0, "max_completion_tokens": 512}, "test"))
        assert result["scoring_details"]["termination"] == "too_many_tool_errors"
        assert result["correct"] is False

    def test_tool_parse_fenced_and_bare(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark
        fenced = 'Thinking...\n```tool\n{"name": "calculate", "arguments": {"expression": "2+2"}}\n```'
        calls = Tau3AirlineBenchmark._parse_tool_calls(fenced)
        assert calls == [{"name": "calculate", "arguments": {"expression": "2+2"}}]
        bare = 'Let me call {"name": "calculate", "arguments": {"expression": "2+2"}} now'
        calls = Tau3AirlineBenchmark._parse_tool_calls(bare)
        assert calls[0]["name"] == "calculate"


# ── Request shaping (chat-template compat) ──────────────────────────

class TestRequestMessages:
    def test_strips_leading_greeting(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark as T
        msgs = T._request_messages("SYS", [
            {"role": "assistant", "content": "Hi! How can I help you today?"},
            {"role": "user", "content": "Cancel my flight."},
        ])
        assert [m["role"] for m in msgs] == ["system", "user"]

    def test_empty_when_no_user_message(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark as T
        assert T._request_messages("SYS", [
            {"role": "assistant", "content": "Hi!"}]) == []
        assert T._request_messages("SYS", []) == []

    def test_user_first_history_untouched(self):
        from backend.benchmarks.taubench_airline import Tau3AirlineBenchmark as T
        conv = [{"role": "user", "content": "Hi."},
                {"role": "assistant", "content": "Hello."}]
        assert T._request_messages("SYS", conv) == [{"role": "system", "content": "SYS"}] + conv


# ── Registration ────────────────────────────────────────────────────

class TestRegistration:
    def test_registered_everywhere(self):
        from backend.config import BENCH_NAMES, BENCHMARK_META, DATASETS, BENCHMARKS
        from backend.operations import BENCHMARK_CLASSES, _instantiate_benchmark
        assert "Tau3-Airline" in BENCH_NAMES
        assert BENCHMARK_META["Tau3-Airline"]["samples"] == 50
        assert not BENCHMARK_META["Tau3-Airline"]["docker"]
        assert "Tau3-Airline" in DATASETS
        assert "Tau3-Airline" in BENCHMARK_CLASSES
        bench = _instantiate_benchmark("Tau3-Airline", MagicMock(), MagicMock(), False)
        assert type(bench).__name__ == "Tau3AirlineBenchmark"
        labels = [label for label, name in BENCHMARKS if name == "Tau3-Airline"]
        assert labels and "50" in labels[0]
