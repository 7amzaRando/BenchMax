import json
import logging
import re
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark
from backend.sandbox.safe_executor import check_correctness_livecodebench

logger = logging.getLogger(__name__)


def _build_prompt(question_content: str, starter_code: str) -> str:
    prompt = f"### Question:\n{question_content}\n\n"
    if starter_code and starter_code.strip():
        prompt += (
            "### Format: You will use the following starter code to write the solution "
            "to the problem and enclose your code within delimiters.\n"
        )
        prompt += f"```python\n{starter_code}\n```\n\n"
    else:
        prompt += (
            "### Format: Read the inputs from stdin solve the problem and write the "
            "answer to stdout (do not directly test on the sample inputs). Enclose your "
            "code within delimiters as follows.\n"
        )
        prompt += "```python\n# YOUR CODE HERE\n```\n\n"
    prompt += "### Answer: (use the provided format with backticks)\n\n"
    return prompt


def _extract_code(text: str) -> str:
    """Extract Python code from model output."""
    if not text:
        return ""
    matches = re.findall(r"```python\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()
    matches = re.findall(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if matches:
        return matches[0].strip()
    lines = text.splitlines()
    code_lines = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if any(s.startswith(kw) for kw in ['def ', 'class ', 'import ', 'from ',
                                            'for ', 'while ', 'if ', 'return ']):
            code_lines.append(line)
        elif code_lines and len(code_lines) > 1:
            return '\n'.join(code_lines).strip()
    return text.strip()


class LiveCodeBenchBenchmark(BaseBenchmark):

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("livecodebench_full.json", fetch_hint="Run 'scripts/fetch_livecodebench.py' to download it.")
        raw = self._load_json_cached(path)
        for s in raw:
            s.setdefault("task_id", s.get("question_id", "unknown"))
        return raw

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        question_content = sample.get("question_content", "")
        starter_code = sample.get("starter_code", "")
        prompt = _build_prompt(question_content, starter_code)
        task_id = sample.get("question_id", "unknown")

        system_prompt = (
            "You are an expert Python programmer. You will be given a question "
            "(problem specification) and will generate a correct Python program "
            "that matches the specification and passes all tests."
        )

        gen = await self._generate(prompt, params, model_name)

        raw_response = gen["raw_response"]
        answer_content = gen["answer_content"]

        extracted_code = _extract_code(answer_content)
        if not extracted_code:
            extracted_code = _extract_code(raw_response)
        if not extracted_code:
            thinking = gen.get("thinking_content", "")
            extracted_code = _extract_code(thinking)

        cat = sample.get("difficulty", "unknown")
        if not extracted_code:
            return self._result(prompt, gen, error_message="No valid Python code extracted",
                                scoring_details={"category": cat, "platform": sample.get("platform", ""), "difficulty": cat})

        input_output = sample.get("input_output", "{}")
        logger.info(f"Running LiveCodeBench code execution for {task_id}")
        try:
            result = check_correctness_livecodebench(
                code=extracted_code,
                input_output=input_output,
                timeout=10.0,
            )
            correct = result["passed"]
            error_msg = None if result["passed"] else result["result"]
        except Exception as e:
            return self._result(prompt, gen, extracted_code=extracted_code,
                                error_message=f"Execution error: {str(e)}",
                                scoring_details={"category": cat, "platform": sample.get("platform", ""), "difficulty": cat})

        return self._result(prompt, gen, extracted_code=extracted_code,
                            correct=correct, error_message=error_msg,
                            scoring_details={"category": cat, "platform": sample.get("platform", ""), "difficulty": cat})

    def generate_diff(self, sample: dict, result_data: dict) -> str:
        import html as html_mod, json
        code = result_data.get("extracted_code", "")
        raw = result_data.get("raw_response", "")
        parts = ["<p><strong>LiveCodeBench — Test-Based Scoring</strong></p>"]
        title = sample.get("question_title", "")
        content = sample.get("question_content", "")
        if title or content:
            parts.append("<p><strong>Question:</strong></p>")
            if title:
                parts.append(f"<p><code>{html_mod.escape(str(title))}</code></p>")
            if content:
                q = str(content)
                q = (q[:3000] + "…") if len(q) > 3000 else q
                parts.append(f"<pre>{html_mod.escape(q)}</pre>")
        io_str = sample.get("input_output", "{}")
        try:
            io = json.loads(io_str) if isinstance(io_str, str) else (io_str or {})
            fn_name = io.get("fn_name", "") or ""
            inputs = io.get("inputs", []) or []
            outputs = io.get("outputs", []) or []
            parts.append(f"<p>Function: <code>{html_mod.escape(str(fn_name))}</code> — {len(inputs)} test case(s)</p>")
            for i, (inp, out) in enumerate(zip(inputs, outputs)):
                parts.append(f"<pre><b>Test {i}:</b>\n  Input:    {html_mod.escape(str(inp))}\n  Expected: {html_mod.escape(str(out))}</pre>")
        except Exception:
            logger.warning("Could not parse LiveCodeBench test cases", exc_info=True)
            parts.append("<p>Could not parse test cases.</p>")
        if code:
            parts.append("<p><strong>Extracted Code:</strong></p>")
            parts.append(f"<pre>{html_mod.escape(code)}</pre>")
        elif raw:
            parts.append("<p><strong>Raw Response:</strong></p>")
            parts.append(f"<pre>{html_mod.escape(raw[:2000])}</pre>")
        return "".join(parts)
