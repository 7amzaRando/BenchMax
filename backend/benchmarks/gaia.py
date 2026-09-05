"""GAIA benchmark — General AI Assistants (validation set).

GAIA evaluates models on real-world questions requiring multi-step reasoning,
tool use (web search, file parsing, calculation), and autonomous problem solving.

This implementation extends MultiTurnBenchmark and provides two tools:
- calculator: evaluate math expressions safely
- search: look up facts from a built-in knowledge base

The model must chain tool calls across multiple turns to reach the answer.
Scoring: Exact match after normalization (lowercase, strip, collapse whitespace).
"""
import ast
import json
import operator
import re
import logging
from typing import Any, Dict, List

from backend.benchmarks.multi_turn_base import MultiTurnBenchmark
from backend.benchmarks.base import resolve_data_file

logger = logging.getLogger(__name__)

# Safe math operators for calculator tool
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> float:
    """Evaluate a math expression safely (no imports, no function calls)."""
    tree = ast.parse(expr.strip(), mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Not a number: {node.value!r}")
        elif isinstance(node, ast.BinOp):
            op = _SAFE_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op = _SAFE_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(_eval(node.operand))
        else:
            raise ValueError(f"Unsupported expression: {type(node).__name__}")

    return _eval(tree)


# Built-in knowledge base for search tool (simulated web search)
# Maps lowercase keys to fact strings. In a real implementation this would
# query a search engine; here we provide facts needed by the hard samples.
_KNOWLEDGE_BASE = {
    "eiffel tower height": "The Eiffel Tower is 330 meters tall (including antenna). Without antenna, it is 300 meters.",
    "eiffel tower location": "The Eiffel Tower is located in Paris, France, on the Champ de Mars.",
    "eiffel tower built": "The Eiffel Tower was built from 1887 to 1889 for the 1889 World's Fair.",
    "population of france": "The population of France is approximately 68 million people (2024 estimate).",
    "population of paris": "The population of Paris proper is approximately 2.1 million. The metro area has about 12 million.",
    "area of france": "The total area of France is approximately 643,801 square kilometers.",
    "largest country by area": "Russia is the largest country by area at 17.1 million sq km.",
    "speed of light": "The speed of light in vacuum is 299,792,458 meters per second.",
    "avogadro number": "Avogadro's number is approximately 6.022 x 10^23.",
    "water boiling point": "Water boils at 100 degrees Celsius (212 Fahrenheit) at standard pressure.",
    "water density": "The density of water is approximately 1000 kg/m^3 at 4 degrees Celsius.",
    "g earth": "The acceleration due to gravity on Earth is approximately 9.81 m/s^2.",
    "g moon": "The acceleration due to gravity on the Moon is approximately 1.62 m/s^2.",
    "earth mass": "The mass of Earth is approximately 5.972 x 10^24 kg.",
    "earth radius": "The radius of Earth is approximately 6,371 km.",
    "australia population": "The population of Australia is approximately 26 million.",
    "australia capital": "The capital of Australia is Canberra.",
    "japan population": "The population of Japan is approximately 125 million.",
    "japan capital": "The capital of Japan is Tokyo.",
    "deeper mariana": "The Challenger Deep in the Mariana Trench is approximately 10,935 meters deep.",
    "atomic number gold": "Gold has atomic number 79.",
    "atomic number silver": "Silver has atomic number 47.",
    "atomic number iron": "Iron has atomic number 26.",
    "tallest building": "The Burj Khalifa in Dubai is the tallest building at 828 meters.",
    "longest river": "The Nile River is the longest river at approximately 6,650 km.",
    "boiling point celsius": "Water boils at 100 degrees Celsius at standard pressure.",
    "freezing point celsius": "Water freezes at 0 degrees Celsius at standard pressure.",
}


def _normalize_answer(text: str) -> str:
    """Normalize an answer for comparison: lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(".")
    return text


def _extract_final_answer(response: str) -> str:
    """Extract the final answer from a model response.

    Looks for common answer patterns:
    - "Answer: ..." or "The answer is ..."
    - Number in bold (**226,611**)
    - "approximately X" pattern
    - Last standalone number in the response
    - Last line if short
    - Full response if short enough
    """
    if not response:
        return ""

    # Strip markdown bold for easier parsing
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", response)

    # Try "Answer: ..." pattern
    m = re.search(r"(?:answer|final answer|result)\s*[:=]\s*(.+?)(?:\n|$)", clean, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Try "The answer is ..." pattern
    m = re.search(r"(?:the answer is|the final answer is)\s+(.+?)(?:\n|$)", clean, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Try "approximately X" pattern (after bold is stripped)
    m = re.search(r"(?:approximately|about|roughly|is)\s+([\d,]+(?:\.\d+)?)\s*(?:joules|J|meters|m|km|people)?", clean, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", "")

    # Try bold number (original response with **)
    m = re.search(r"\*\*([\d,]+(?:\.\d+)?)\*\*", response)
    if m:
        return m.group(1).replace(",", "")

    # Try last standalone number in the cleaned response
    numbers = re.findall(r"(?<!\w)([\d,]+(?:\.\d+)?)(?!\w)", clean)
    if numbers:
        return numbers[-1].replace(",", "")

    # If response is short (< 200 chars), use the whole thing
    if len(response.strip()) < 200:
        return response.strip()

    # Otherwise, use the last non-empty line
    lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
    if lines:
        return lines[-1]

    return response.strip()


# Tool definitions exposed to the model
GAIA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression. Supports +, -, *, /, //, %, **. Returns a number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate, e.g. '2 + 2' or '(3.14 * 10**2) / 4'"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search for a fact. Returns relevant information from the knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query, e.g. 'speed of light' or 'population of France'"
                    }
                },
                "required": ["query"]
            }
        }
    },
]


class GAIABenchmark(MultiTurnBenchmark):
    """GAIA — General AI Assistants benchmark (validation set).

    Evaluates multi-step reasoning with tool use. The model receives a question
    and must use calculator and search tools across multiple turns to reach
    the answer.
    """

    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset(
            "gaia_full.json",
            fetch_hint="Install via the dataset installer or run scripts/fetch_gaia.py",
        )
        raw = self._load_json_cached(path)
        # Map fetched rows onto the MultiTurnBenchmark sample schema. This
        # also guarantees the turn-0 request starts with a user message —
        # strict chat templates (e.g. ornith) reject user-less histories
        # with "No user query found in messages".
        return [{
            "task_id": s.get("task_id", f"gaia/{i}"),
            "turns": [{"role": "user", "content": s.get("question", "")}],
            "ground_truth": s.get("answer", ""),
            "tools": GAIA_TOOLS,
            "max_turns": 10,
            "max_wall_clock_sec": 900,
            "category": s.get("category", "unknown"),
            "level": s.get("level", ""),
            "year": s.get("year", ""),
        } for i, s in enumerate(raw)]

    async def evaluate_turn(
        self,
        turn_idx: int,
        conversation: List[Dict[str, str]],
        sample: Dict[str, Any],
        params: Dict[str, Any],
        model_name: str,
    ) -> Dict[str, Any]:
        """Process a single conversation turn.

        Sends the full conversation history to the model with tool definitions.
        Parses the response for tool calls.
        """
        # Build messages array with full conversation history
        messages = list(conversation)  # copy to avoid mutation

        # Add system prompt on first turn
        if turn_idx == 0:
            tools = sample.get("tools") or GAIA_TOOLS
            tools_desc = self._format_tools_for_prompt(tools)
            system_msg = {
                "role": "system",
                "content": (
                    "You are a helpful assistant that solves questions step by step. "
                    "You have access to the following tools:\n\n"
                    f"{tools_desc}\n\n"
                    "To use a tool, output a JSON block on its own line:\n"
                    '```tool\n{"name": "tool_name", "arguments": {"param": "value"}}\n```\n\n'
                    "After receiving tool results, continue reasoning. "
                    "When you have the final answer, output it on the last line as:\n"
                    "Answer: <your answer>"
                ),
            }
            messages.insert(0, system_msg)

        # Generate response
        gen = await self._generate_chat(
            messages,
            params,
            model_name,
        )

        response = gen.get("answer_content", "") or gen.get("raw_response", "")

        # Parse tool calls from response
        tool_calls = self._parse_tool_calls(response)

        # Check if model indicated it's done (has "Answer:" line)
        done = bool(re.search(r"(?:^|\n)\s*Answer:\s*", response, re.IGNORECASE))

        return {
            "response": response,
            "tool_calls": tool_calls if tool_calls else None,
            "done": done,
            "gen": gen,
        }

    def _format_tools_for_prompt(self, tools: List[Dict]) -> str:
        """Format tool definitions into a human-readable prompt string."""
        lines = []
        for tool in tools:
            func = tool.get("function", tool)
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])

            lines.append(f"- {name}: {desc}")
            for pname, pinfo in params.items():
                req = "(required)" if pname in required else "(optional)"
                lines.append(f"    {pname}: {pinfo.get('description', '')} {req}")
        return "\n".join(lines)

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from model response.

        Looks for JSON blocks in ```tool ... ``` fences, or bare JSON objects
        with "name" and "arguments" keys.
        """
        tool_calls = []

        # Strategy 1: Find ```tool ... ``` blocks
        pattern = r"```tool\s*\n(.*?)\n\s*```"
        for match in re.finditer(pattern, response, re.DOTALL):
            try:
                call = json.loads(match.group(1).strip())
                if "name" in call:
                    tool_calls.append({
                        "name": call["name"],
                        "arguments": call.get("arguments", {}),
                    })
            except (json.JSONDecodeError, KeyError):
                continue

        # Strategy 2: Find bare JSON objects with name/arguments (if no fenced blocks found)
        if not tool_calls:
            for match in re.finditer(r"\{[^{}]*\"name\"\s*:\s*\"(\w+)\"[^{}]*\}", response):
                try:
                    obj = json.loads(match.group(0))
                    if "name" in obj:
                        tool_calls.append({
                            "name": obj["name"],
                            "arguments": obj.get("arguments", {}),
                        })
                except (json.JSONDecodeError, KeyError):
                    continue

        return tool_calls

    async def execute_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        sample: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Execute tool calls and return tool result messages.

        Supports:
        - calculator: evaluates math expressions
        - search: looks up facts from built-in knowledge base
        """
        results = []
        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("arguments", {})

            if name == "calculator":
                expression = args.get("expression", "")
                try:
                    value = _safe_eval(expression)
                    # Format nicely: int if whole number, else float
                    if isinstance(value, float) and value == int(value):
                        value = int(value)
                    results.append({
                        "role": "tool",
                        "content": f"calculator({expression}) = {value}",
                    })
                except Exception as e:
                    results.append({
                        "role": "tool",
                        "content": f"calculator({expression}) error: {e}",
                    })

            elif name == "search":
                query = args.get("query", "")
                result_text = self._search_knowledge(query)
                results.append({
                    "role": "tool",
                    "content": f"search({query}) = {result_text}",
                })

            else:
                results.append({
                    "role": "tool",
                    "content": f"Error: Unknown tool '{name}'",
                })

        return results

    def _search_knowledge(self, query: str) -> str:
        """Search the built-in knowledge base for a fact.

        Uses fuzzy matching: checks if any key is contained in the query
        or vice versa.
        """
        query_lower = query.lower().strip()

        # Exact match
        if query_lower in _KNOWLEDGE_BASE:
            return _KNOWLEDGE_BASE[query_lower]

        # Partial match: query contains key
        for key, value in _KNOWLEDGE_BASE.items():
            if key in query_lower:
                return value

        # Partial match: key contains query
        for key, value in _KNOWLEDGE_BASE.items():
            if query_lower in key:
                return value

        # Word overlap match
        query_words = set(query_lower.split())
        best_score = 0
        best_value = None
        for key, value in _KNOWLEDGE_BASE.items():
            key_words = set(key.split())
            overlap = len(query_words & key_words)
            if overlap > best_score:
                best_score = overlap
                best_value = value

        if best_score > 0 and best_value:
            return best_value

        return f"No information found for '{query}'"

    def score(
        self,
        sample: Dict[str, Any],
        conversation: List[Dict[str, str]],
        final_response: str,
    ) -> Dict[str, Any]:
        """Score the completed conversation.

        Extracts the final answer by scanning ALL assistant messages (not just
        the last one), since the model may output the answer in an earlier turn
        and then generate empty/continuation turns.
        """
        ground_truth = sample.get("ground_truth", "")

        # Scan all assistant messages for the best answer
        extracted = ""
        for msg in conversation:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if content.strip():
                    candidate = _extract_final_answer(content)
                    if candidate:
                        extracted = candidate

        # If nothing found from extraction, try the last non-empty assistant message
        if not extracted:
            for msg in reversed(conversation):
                if msg.get("role") == "assistant" and msg.get("content", "").strip():
                    extracted = msg["content"].strip()
                    break

        normalized_extracted = _normalize_answer(extracted)
        normalized_truth = _normalize_answer(ground_truth)

        # Exact match
        correct = normalized_extracted == normalized_truth

        # Containment checks (only when answer is substantive, not a bare number prefix)
        if not correct and normalized_truth and len(normalized_truth) > 3 and normalized_truth in normalized_extracted:
            correct = True
        if not correct and normalized_extracted and len(normalized_extracted) > 3 and normalized_extracted in normalized_truth:
            correct = True

        # Count tool calls
        tool_call_count = 0
        for msg in conversation:
            if msg.get("role") == "assistant":
                calls = self._parse_tool_calls(msg.get("content", ""))
                tool_call_count += len(calls)

        turns_used = len([m for m in conversation if m["role"] == "assistant"])

        cat = sample.get("category", sample.get("level", "unknown"))
        return {
            "correct": correct,
            "score": 1.0 if correct else 0.0,
            "details": {
                "ground_truth": ground_truth,
                "extracted_answer": extracted,
                "normalized_expected": normalized_truth,
                "normalized_got": normalized_extracted,
                "turns_used": turns_used,
                "tool_calls_made": tool_call_count,
                "category": cat,
            },
        }
