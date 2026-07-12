import json
import logging
import re
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file
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


class LiveCodeBenchBenchmark(BaseBenchmark):

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "livecodebench_mini.json" if self.quick_test else "livecodebench_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            logger.warning("Full LiveCodeBench dataset not found, falling back to mini")
            fallback = "livecodebench_mini.json"
            self.dataset_path = resolve_data_file(__file__, fallback)
        if not self.dataset_path:
            raise FileNotFoundError(
                "LiveCodeBench dataset not found. "
                "Run 'scripts/fetch_livecodebench.py' to download it."
            )
        return self._load_json_cached(self.dataset_path)

    def _extract_code(self, text: str) -> str:
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

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        question_content = sample["question_content"]
        starter_code = sample.get("starter_code", "")
        prompt = _build_prompt(question_content, starter_code)
        task_id = sample.get("question_id", "unknown")

        system_prompt = (
            "You are an expert Python programmer. You will be given a question "
            "(problem specification) and will generate a correct Python program "
            "that matches the specification and passes all tests."
        )

        generation = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt", system_prompt),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        raw_response = generation["raw_response"]
        answer_content = generation["answer_content"]

        extracted_code = self._extract_code(answer_content)
        if not extracted_code:
            extracted_code = self._extract_code(raw_response)
        if not extracted_code:
            thinking = generation.get("thinking_content", "")
            extracted_code = self._extract_code(thinking)

        if not extracted_code:
            return {
                "prompt": prompt,
                "raw_response": raw_response,
                "extracted_code": "",
                "correct": False,
                "error_message": "No valid Python code extracted",
                "elapsed_time": generation["elapsed_time"],
                "tps": generation["tps"],
                "ttft": generation["ttft"],
                "thinking_tokens": generation["thinking_tokens"],
                "response_tokens": generation["response_tokens"],
            }

        input_output = sample.get("input_output", "{}")
        logger.info(f"Running LiveCodeBench code execution for {task_id}")
        try:
            result = check_correctness_livecodebench(
                code=extracted_code,
                input_output=input_output,
                timeout=10.0,
            )
            correct = result["passed"]
            error_msg = "" if result["passed"] else result["result"]
        except Exception as e:
            return {
                "prompt": prompt,
                "raw_response": raw_response,
                "extracted_code": extracted_code,
                "correct": False,
                "error_message": f"Execution error: {str(e)}",
                "elapsed_time": generation["elapsed_time"],
                "tps": generation["tps"],
                "ttft": generation["ttft"],
                "thinking_tokens": generation["thinking_tokens"],
                "response_tokens": generation["response_tokens"],
            }

        return {
            "prompt": prompt,
            "raw_response": raw_response,
            "extracted_code": extracted_code,
            "correct": correct,
            "error_message": error_msg,
            "elapsed_time": generation["elapsed_time"],
            "tps": generation["tps"],
            "ttft": generation["ttft"],
            "thinking_tokens": generation["thinking_tokens"],
            "response_tokens": generation["response_tokens"],
        }
