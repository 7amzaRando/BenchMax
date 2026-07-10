import logging
import re
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.sandbox.docker_executor import DockerExecutor

logger = logging.getLogger(__name__)

class BigCodeBenchBenchmark(BaseBenchmark):
    requires_docker = True

    def __init__(self, db, client, quick_test=False, hard=False):
        super().__init__(db, client, quick_test)
        self.executor = DockerExecutor()
        self.hard = hard

    def load_dataset(self) -> List[Dict[str, Any]]:
        suffix = "_hard" if self.hard else ""
        filename = f"bigcodebench{suffix}_mini.json" if self.quick_test else f"bigcodebench{suffix}_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            suffix_str = "-Hard" if self.hard else ""
            logger.warning(f"Full BigCodeBench{suffix_str} dataset not found, falling back to mini dataset")
            fallback = f"bigcodebench{suffix}_mini.json"
            self.dataset_path = resolve_data_file(__file__, fallback)
        if not self.dataset_path:
            raise FileNotFoundError(
                f"BigCodeBench{'-Hard' if self.hard else ''} dataset not found. "
                f"Run 'scripts/fetch_bigcodebench{'_hard' if self.hard else ''}.py' to download it."
            )
        return self._load_json_cached(self.dataset_path)

    def _extract_python_code(self, text: str, entry_point: str) -> str:
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
            if not s or s.startswith("#"):
                continue
            if any(s.startswith(kw) for kw in ['def ', 'class ', 'for ', 'if ', 'while ',
                                                'return ', 'import ', 'from ', 'with ']):
                code_lines.append(line)
            elif code_lines and len(code_lines) > 1:
                return '\n'.join(code_lines).strip()
        return text.strip()

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample["prompt"]
        entry_point = sample["entry_point"]
        test_suite = sample.get("test", "")
        task_id = sample["task_id"]

        generation = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens", ["\nif __name__"]),
            model_name=model_name,
        )

        raw_response = generation["raw_response"]
        answer_content = generation["answer_content"]

        extracted_code = self._extract_python_code(answer_content, entry_point)
        if not extracted_code or entry_point not in extracted_code:
            extracted_code = self._extract_python_code(raw_response, entry_point)
        if not extracted_code or entry_point not in extracted_code:
            thinking = generation.get("thinking_content", "")
            if thinking:
                extracted_code = self._extract_python_code(thinking, entry_point)

        if not extracted_code or entry_point not in extracted_code:
            return {
                "prompt": prompt,
                "raw_response": raw_response,
                "extracted_code": extracted_code or "",
                "correct": False,
                "error_message": "No valid code extracted",
                "elapsed_time": generation["elapsed_time"],
                "tps": generation["tps"],
                "ttft": generation["ttft"],
                "thinking_tokens": generation["thinking_tokens"],
                "response_tokens": generation["response_tokens"],
            }

        if not test_suite or not test_suite.strip():
            return {
                "prompt": prompt,
                "raw_response": raw_response,
                "extracted_code": extracted_code,
                "correct": False,
                "error_message": "No test suite available for this sample",
                "elapsed_time": generation["elapsed_time"],
                "tps": generation["tps"],
                "ttft": generation["ttft"],
                "thinking_tokens": generation["thinking_tokens"],
                "response_tokens": generation["response_tokens"],
            }

        test_script = f"{extracted_code}\n\n{test_suite}\n\nif __name__ == '__main__':\n    unittest.main(exit=True)\n"

        label = "BigCodeBench-Hard" if self.hard else "BigCodeBench"
        logger.info(f"Running {label} sandbox for {task_id}")
        try:
            sandbox_res = self.executor.execute_python_code(test_script, timeout=min(10.0, max(5.0, 3.0 + len(extracted_code) / 500)), benchmark_name="BigCodeBench")
        except Exception as e:
            return {
                "prompt": prompt,
                "raw_response": raw_response,
                "extracted_code": extracted_code,
                "correct": False,
                "error_message": f"Sandbox error: {str(e)}",
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
            "correct": sandbox_res["success"],
            "error_message": sandbox_res.get("error") or sandbox_res.get("stderr"),
            "elapsed_time": generation["elapsed_time"],
            "tps": generation["tps"],
            "ttft": generation["ttft"],
            "thinking_tokens": generation["thinking_tokens"],
            "response_tokens": generation["response_tokens"],
        }

    def cleanup(self) -> None:
        self.executor.cleanup()
