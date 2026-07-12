import logging
import re
import textwrap
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.sandbox.safe_executor import check_correctness_bigcodebench

logger = logging.getLogger(__name__)

class BigCodeBenchBenchmark(BaseBenchmark):

    def __init__(self, db, client, quick_test=False, hard=False):
        super().__init__(db, client, quick_test)
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
        matches = re.findall(r"```python\r?\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if matches:
            code = textwrap.dedent(matches[0])
            if code.strip():
                return code.strip()
        matches = re.findall(r"```\r?\n(.*?)```", text, re.DOTALL)
        if matches:
            code = textwrap.dedent(matches[0])
            if code.strip():
                return code.strip()
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
        if entry_point:
            pat = re.compile(r'def\s+' + re.escape(entry_point) + r'\s*\(', re.DOTALL)
            m = pat.search(text)
            if m:
                start = m.start()
                rest = text[start:]
                depth = 0
                func_lines = []
                for line in rest.splitlines():
                    stripped = line.strip()
                    if not stripped and not func_lines:
                        continue
                    func_lines.append(line)
                    if stripped.endswith(':'):
                        depth += 1
                    elif depth > 0 and stripped.startswith(('def ', 'class ', '@', '"""', "'''", 'async def')):
                        break
                if len(func_lines) > 1:
                    return textwrap.dedent('\n'.join(func_lines))
        return text.strip()

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample.get("prompt", "")
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

        label = "BigCodeBench-Hard" if self.hard else "BigCodeBench"
        logger.info(f"Running {label} code execution for {task_id}")
        try:
            timeout = min(10.0, max(5.0, 3.0 + len(extracted_code) / 500))
            result = check_correctness_bigcodebench(
                entry_point=entry_point,
                code=extracted_code,
                test_code=test_suite,
                timeout=timeout,
            )
            correct = result["passed"]
            error_msg = "" if result["passed"] else result["result"]
            if not correct and result["details"]:
                error_msg = "; ".join(result["details"][:3])
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
