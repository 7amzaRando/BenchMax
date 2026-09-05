import logging
import re
import textwrap
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.humaneval import extract_python_code
from backend.sandbox.safe_executor import check_correctness_bigcodebench

logger = logging.getLogger(__name__)

class BigCodeBenchBenchmark(BaseBenchmark):

    def __init__(self, db, client, quick_test=False, hard=False):
        super().__init__(db, client, quick_test)
        self.hard = hard

    def load_dataset(self) -> List[Dict[str, Any]]:
        suffix = "_hard" if self.hard else ""
        full_name = f"bigcodebench{suffix}_full.json"
        mini_name = f"bigcodebench{suffix}_mini.json"
        suffix_str = "-Hard" if self.hard else ""
        fetch_hint = f"Run 'scripts/fetch_bigcodebench{'_hard' if self.hard else ''}.py' to download it."
        path = self._resolve_dataset(full_name, mini_name=mini_name, fetch_hint=fetch_hint)
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample.get("prompt", "")
        entry_point = sample.get("entry_point", "")
        test_suite = sample.get("test", "")
        task_id = sample.get("task_id", "")

        generation = await self._generate(prompt, params, model_name, stop_tokens=["\nif __name__"])

        raw_response = generation["raw_response"]
        answer_content = generation["answer_content"]

        extracted_code = extract_python_code(answer_content, entry_point)
        if not extracted_code or entry_point not in extracted_code:
            extracted_code = extract_python_code(raw_response, entry_point)
        if not extracted_code or entry_point not in extracted_code:
            thinking = generation.get("thinking_content", "")
            if thinking:
                extracted_code = extract_python_code(thinking, entry_point)

        if not extracted_code or entry_point not in extracted_code:
            return self._result(prompt, generation, extracted_code=extracted_code or "",
                                error_message="No valid code extracted")

        if not test_suite or not test_suite.strip():
            return self._result(prompt, generation, extracted_code=extracted_code,
                                error_message="No test suite available for this sample")

        label = "BigCodeBench-Hard" if self.hard else "BigCodeBench"
        logger.info(f"Running {label} code execution for {task_id}")
        try:
            timeout = min(10.0, max(5.0, 3.0 + len(extracted_code) / 500))
            result = check_correctness_bigcodebench(
                code=extracted_code,
                test_code=test_suite,
                timeout=timeout,
                block_child_processes=False,
                block_network=False,
            )
            correct = result["passed"]
            error_msg = None if result["passed"] else result["result"]
            if not correct and result["details"]:
                error_msg = "; ".join(result["details"][:3])
        except Exception as e:
            return self._result(prompt, generation, extracted_code=extracted_code,
                                error_message=f"Execution error: {str(e)}")

        return self._result(prompt, generation, extracted_code=extracted_code,
                            correct=correct, error_message=error_msg)
