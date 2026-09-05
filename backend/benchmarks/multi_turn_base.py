"""Base class for multi-turn agentic benchmarks.

Multi-turn benchmarks evaluate models on conversations that require multiple
exchanges — tool-use loops, iterative coding, research tasks, or multi-step
reasoning. Unlike single-turn benchmarks that send one prompt and score one
response, multi-turn benchmarks maintain a conversation history and may
execute tools between turns.

Subclasses must implement:
    - load_dataset(): return samples with "turns" and "ground_truth"
    - evaluate_turn(): process a single conversation turn
    - score(): evaluate the completed conversation

The base class handles:
    - Conversation loop management (append assistant + tool results)
    - Turn-level progress tracking via run.current_index
    - Pause/halt between turns (conversation saved to memory)
    - Token aggregation across all turns
    - Anti-loop detection (delegated to client per generation call)
"""

import logging
import threading
import time
from abc import abstractmethod
from typing import Any, Dict, List

from backend.benchmarks.base import BaseBenchmark

logger = logging.getLogger(__name__)

# Live turn tracking for poll/status — updated per turn, read by operations.poll()
_live_turn_state: Dict[str, Any] = {}
_live_turn_lock = threading.Lock()

def get_live_turn_state() -> Dict[str, Any]:
    """Return a snapshot of the current multi-turn progress for live polling."""
    with _live_turn_lock:
        return dict(_live_turn_state)

def _set_live_turn(run_id: int | None, turn: int, max_turns: int, elapsed: float) -> None:
    with _live_turn_lock:
        if run_id is not None:
            _live_turn_state["run_id"] = run_id
        _live_turn_state["turn"] = turn
        _live_turn_state["max_turns"] = max_turns
        _live_turn_state["elapsed"] = elapsed
        _live_turn_state["ts"] = time.time()

def _clear_live_turn() -> None:
    with _live_turn_lock:
        _live_turn_state.clear()

# Default limits for multi-turn conversations
_DEFAULT_MAX_CONTEXT_TOKENS = 32768  # Fallback if model metadata unavailable
_DEFAULT_MAX_WALL_CLOCK_SEC = 120   # Hard timeout per sample


class MultiTurnBenchmark(BaseBenchmark):
    """Base class for multi-turn agentic benchmarks.

    Sample schema (returned by load_dataset()):
        {
            "task_id": str,
            "turns": [{"role": "user", "content": "..."}],  # initial user messages
            "ground_truth": any,          # expected final state/answer
            "tools": [dict] | None,       # optional tool definitions
            "max_turns": int,             # max conversation turns (default: 10)
            "metadata": dict | None,      # optional difficulty/category info
        }

    Subclass contract:
        - evaluate_turn() receives the full conversation so far and must
          return {"response": str, "tool_calls": list|None, "done": bool}.
        - score() receives the sample, full conversation, and final response,
          and must return {"correct": bool, "score": float, "details": dict}.
    """

    @abstractmethod
    def load_dataset(self) -> List[Dict[str, Any]]:
        """Load and return the dataset. Each sample must have at minimum:
        task_id, turns (list of initial user messages), ground_truth.
        """
        pass

    @abstractmethod
    async def evaluate_turn(
        self,
        turn_idx: int,
        conversation: List[Dict[str, str]],
        sample: Dict[str, Any],
        params: Dict[str, Any],
        model_name: str,
    ) -> Dict[str, Any]:
        """Process a single conversation turn.

        Args:
            turn_idx: Current turn index (0-based).
            conversation: Full conversation history so far (mutable list).
            sample: The dataset sample being evaluated.
            params: Run parameters (temperature, max_tokens, etc.).
            model_name: Model ID.

        Returns:
            {
                "response": str,           # Model's text response for this turn
                "tool_calls": list|None,    # Tool calls the model wants to execute
                "done": bool,              # Whether the conversation should end
                "gen": dict|None,          # Optional: raw gen dict from _generate_chat()
                                         # (used by base class to accumulate token counts)
            }
        """
        pass

    @abstractmethod
    def score(
        self,
        sample: Dict[str, Any],
        conversation: List[Dict[str, str]],
        final_response: str,
    ) -> Dict[str, Any]:
        """Score the completed conversation.

        Args:
            sample: The original dataset sample.
            conversation: Full conversation history (all turns).
            final_response: The model's final response text.

        Returns:
            {
                "correct": bool,
                "score": float,       # 0.0 to 1.0
                "details": dict,      # Scoring details (stored in scoring_details column)
            }
        """
        pass

    async def execute_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        sample: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Execute tool calls and return tool result messages.

        Default implementation returns error messages (no tools executed).
        Override in subclasses that support specific tool types.

        Args:
            tool_calls: List of tool call dicts from the model.
            sample: The dataset sample (for context).

        Returns:
            List of {"role": "tool", "content": str} messages to append.
        """
        results = []
        for call in tool_calls:
            tool_name = call.get("name", "unknown")
            results.append({
                "role": "tool",
                "content": f"Error: Tool '{tool_name}' is not implemented in this benchmark.",
            })
        return results

    async def _get_model_context_limit(self, model_name: str) -> int:
        """Query LM Studio for the model's actual loaded context window.

        Checks /api/v1/models for loaded_instances[].config.context_length
        (the actual limit the model was loaded with), then falls back to
        max_context_length. Returns the default fallback if unavailable.
        """
        try:
            # /api/v1/models has loaded_instances with config.context_length
            base = self.client.base_url.rsplit("/v1", 1)[0] if "/v1" in self.client.base_url else self.client.base_url
            url = f"{base}/api/v1/models"
            resp = await self.client._get_client().get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                entries = data.get("models", data.get("data", []))
                for entry in entries:
                    key = entry.get("key", entry.get("id", ""))
                    if model_name not in key and key not in model_name:
                        continue
                    # Check loaded instance config first
                    for inst in entry.get("loaded_instances", []):
                        ctx = inst.get("config", {}).get("context_length")
                        if ctx and ctx > 0:
                            logger.info("Model %s loaded context: %d tokens", model_name, ctx)
                            return ctx
                    # Fall back to max_context_length
                    ctx = entry.get("max_context_length")
                    if ctx and ctx > 0:
                        logger.info("Model %s max context: %d tokens (not loaded)", model_name, ctx)
                        return ctx
        except Exception as e:
            logger.warning("Could not fetch model context limit: %s", e)
        logger.info("Using default context limit: %d tokens", _DEFAULT_MAX_CONTEXT_TOKENS)
        return _DEFAULT_MAX_CONTEXT_TOKENS

    def _truncate_conversation(
        self,
        conversation: List[Dict[str, str]],
        max_tokens: int,
    ) -> List[Dict[str, str]]:
        """Truncate oldest turns when conversation exceeds context window.

        Strategy: Always preserve the system message (first if role=system).
        Drop oldest user/assistant/tool message pairs until estimated tokens
        fit within budget. Estimates tokens as len(text) / 4 (rough heuristic).

        Args:
            conversation: Full conversation history (mutated in place).
            max_tokens: Maximum estimated input tokens before truncation.

        Returns:
            Truncated conversation (same list, modified in place).
        """
        # Estimate total tokens
        total_chars = sum(len(m.get("content", "")) for m in conversation)
        estimated_tokens = total_chars // 4

        if estimated_tokens <= max_tokens:
            return conversation

        logger.warning(
            "Context overflow: ~%d estimated tokens exceeds %d limit, truncating oldest turns",
            estimated_tokens, max_tokens,
        )

        # Preserve system message if present
        system_msg = None
        if conversation and conversation[0].get("role") == "system":
            system_msg = conversation[0]

        # Work with non-system messages
        messages = conversation[1:] if system_msg else conversation

        # Keep dropping oldest user+response pairs until under budget
        # Each "turn" is a user message + assistant response + optional tool results
        while messages:
            current_chars = sum(len(m.get("content", "")) for m in messages)
            if (current_chars // 4) <= max_tokens:
                break

            # Find and drop the oldest user message and everything up to the next user message
            drop_end = 0
            for idx, msg in enumerate(messages):
                if idx > 0 and msg.get("role") == "user":
                    drop_end = idx
                    break
            if drop_end == 0:
                # No more user messages to pair with, drop first message
                drop_end = 1

            messages = messages[drop_end:]

        # Rebuild conversation
        conversation.clear()
        if system_msg:
            conversation.append(system_msg)
        conversation.extend(messages)

        return conversation

    async def evaluate_sample(
        self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str
    ) -> Dict[str, Any]:
        """Run a full multi-turn conversation and score it.

        This implements the standard BaseBenchmark contract. It manages the
        conversation loop, delegates turn processing to evaluate_turn(),
        executes tools, and calls score() when done.

        Safety limits:
        - max_turns: from sample (default 10) — stops the loop
        - max_context_tokens: queried from model metadata, falls back to sample/default
        - max_wall_clock_sec: hard timeout on total sample time (default 120s)
        """
        max_turns = sample.get("max_turns", 10)
        max_wall_clock = sample.get("max_wall_clock_sec", _DEFAULT_MAX_WALL_CLOCK_SEC)
        turns = sample.get("turns", [])

        # Query model's actual context limit from LM Studio metadata
        max_context_tokens = await self._get_model_context_limit(model_name)

        # Build initial conversation from sample's turn list
        conversation: List[Dict[str, str]] = []
        for turn in turns:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            conversation.append({"role": role, "content": content})

        # Extract the initial prompt for the result dict
        initial_prompt = conversation[0]["content"] if conversation else ""

        total_tokens = {"thinking": 0, "response": 0, "prompt": 0}
        total_elapsed = 0.0
        last_tps = 0.0
        last_ttft = 0.0
        sample_start = time.time()
        run_id = params.get("_run_id") or params.get("run_id")

        # Per-turn details for persistence (scoring_details.turns) and live progress
        turn_details: List[Dict[str, Any]] = []
        # Seed with initial user turns (no timing)
        for _t in turns:
            turn_details.append({
                "turn": -1,
                "role": _t.get("role", "user"),
                "content": _t.get("content", "")[:4000],
            })

        for turn_idx in range(max_turns):
            _set_live_turn(run_id, turn_idx + 1, max_turns, time.time() - sample_start)
            # Wall-clock cap
            elapsed_so_far = time.time() - sample_start
            if elapsed_so_far >= max_wall_clock:
                logger.warning(
                    "Wall-clock cap hit at turn %d (%.1fs >= %ds)",
                    turn_idx, elapsed_so_far, max_wall_clock,
                )
                timeout_msg = f"[TIMEOUT: Exceeded {max_wall_clock}s wall-clock limit]"
                conversation.append({
                    "role": "assistant",
                    "content": timeout_msg
                })
                turn_details.append({
                    "turn": turn_idx,
                    "role": "assistant",
                    "content": timeout_msg,
                })
                break

            # Context overflow handling: truncate oldest turns if too long
            conversation = self._truncate_conversation(conversation, max_context_tokens)

            try:
                result = await self.evaluate_turn(
                    turn_idx, conversation, sample, params, model_name
                )
            except Exception as e:
                logger.error(f"evaluate_turn failed at turn {turn_idx}: {e}")
                _clear_live_turn()
                return self._result(
                    initial_prompt,
                    {"elapsed_time": total_elapsed, "tps": last_tps, "ttft": last_ttft,
                     "thinking_tokens": total_tokens["thinking"], "response_tokens": total_tokens["response"],
                     "prompt_tokens": total_tokens["prompt"]},
                    correct=False,
                    error_message=f"Turn {turn_idx} failed: {e}",
                    scoring_details={"turns": turn_details, "error_turn": turn_idx},
                )

            response = result.get("response", "")
            tool_calls = result.get("tool_calls")
            done = result.get("done", False)

            # Accumulate token counts from this turn's generation call
            gen = result.get("gen")
            if gen:
                total_tokens["thinking"] += gen.get("thinking_tokens", 0)
                total_tokens["response"] += gen.get("response_tokens", 0)
                total_tokens["prompt"] += gen.get("prompt_tokens", 0)
                total_elapsed += gen.get("elapsed_time", 0.0)
                last_tps = gen.get("tps", 0.0)
                last_ttft = gen.get("ttft", 0.0)

            # Early stop: if response is empty and no tool calls, model is done.
            # Do NOT append the empty message — it breaks the Jinja chat template
            # on the next turn (LM Studio throws "Cannot perform operation on undefined values").
            if not response.strip() and not tool_calls:
                logger.info("Empty response at turn %d, stopping", turn_idx)
                # Record empty turn for debugging (truncated)
                turn_details.append({
                    "turn": turn_idx,
                    "role": "assistant",
                    "content": "[empty response]",
                    "tps": gen.get("tps", 0.0) if gen else 0.0,
                    "ttft": gen.get("ttft", 0.0) if gen else 0.0,
                    "thinking_tokens": gen.get("thinking_tokens", 0) if gen else 0,
                    "response_tokens": gen.get("response_tokens", 0) if gen else 0,
                    "prompt_tokens": gen.get("prompt_tokens", 0) if gen else 0,
                    "elapsed_time": gen.get("elapsed_time", 0.0) if gen else 0.0,
                })
                break

            # Append assistant response to conversation (only non-empty)
            conversation.append({"role": "assistant", "content": response})

            # Record per-turn details for scoring_details.turns
            turn_details.append({
                "turn": turn_idx,
                "role": "assistant",
                "content": response[:4000],
                "tps": gen.get("tps", 0.0) if gen else 0.0,
                "ttft": gen.get("ttft", 0.0) if gen else 0.0,
                "thinking_tokens": gen.get("thinking_tokens", 0) if gen else 0,
                "response_tokens": gen.get("response_tokens", 0) if gen else 0,
                "prompt_tokens": gen.get("prompt_tokens", 0) if gen else 0,
                "elapsed_time": gen.get("elapsed_time", 0.0) if gen else 0.0,
                "tool_calls": tool_calls,
            })

            # Execute tools if present (before checking done, so score() can see results)
            if tool_calls:
                tool_results = await self.execute_tools(tool_calls, sample)
                conversation.extend(tool_results)
                for tr in tool_results:
                    turn_details.append({
                        "turn": turn_idx,
                        "role": tr.get("role", "tool"),
                        "content": tr.get("content", "")[:2000],
                        "tool": tr.get("tool", tr.get("name", "")),
                    })

            if done:
                break

        _clear_live_turn()

        # Score the conversation
        try:
            score_result = self.score(sample, conversation, conversation[-1]["content"] if conversation else "")
        except Exception as e:
            logger.error(f"score() failed: {e}")
            return self._result(
                initial_prompt,
                {"elapsed_time": total_elapsed, "tps": last_tps, "ttft": last_ttft,
                 "thinking_tokens": total_tokens["thinking"], "response_tokens": total_tokens["response"],
                 "prompt_tokens": total_tokens["prompt"]},
                correct=False,
                error_message=f"Scoring failed: {e}",
                scoring_details={"turns": turn_details},
            )

        # Build the prompt summary (all user turns concatenated)
        prompt_summary = "\n".join(
            m["content"] for m in conversation if m["role"] == "user"
        )

        # Build raw response summary (all assistant turns)
        raw_response = "\n---\n".join(
            m["content"] for m in conversation if m["role"] == "assistant"
        )

        return self._result(
            prompt_summary,
            {
                "elapsed_time": total_elapsed,
                "tps": last_tps,
                "ttft": last_ttft,
                "thinking_tokens": total_tokens["thinking"],
                "response_tokens": total_tokens["response"],
                "prompt_tokens": total_tokens["prompt"],
                "raw_response": raw_response,
            },
            correct=score_result.get("correct", False),
            error_message=None if score_result.get("correct") else score_result.get("details", {}).get("error"),
            scoring_details={
                "score": score_result.get("score", 0.0),
                "turns_used": len([m for m in conversation if m["role"] == "assistant"]),
                "conversation_length": len(conversation),
                "turns": turn_details,
                "max_turns": max_turns,
                **score_result.get("details", {}),
            },
        )


