import re
import logging
from typing import Dict, Any, List

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.benchmarks.aime import extract_aime_answer
from backend.benchmarks.ifeval import CHECKERS

logger = logging.getLogger(__name__)

class LiveBenchBenchmark(BaseBenchmark):
    """
    6-category meta-benchmark:
    - MCQ (regex A-D), math (extract number via AIME answer parser), code (Docker unit test),
      language (string match), data (string match), instruction (rule-based IFEval CHECKERS).
    Only the code category requires Docker.
    """
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)
        self.requires_docker = True
        self._coding_executor = None

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "livebench_mini.json" if self.quick_test else "livebench_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            logger.warning("Full LiveBench dataset not found, falling back to mini dataset")
            fallback = "livebench_mini.json"
            self.dataset_path = resolve_data_file(__file__, fallback)
        if not self.dataset_path:
            raise FileNotFoundError(
                "LiveBench dataset not found. "
                "Run 'scripts/fetch_livebench.py' to download it."
            )
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        category = sample.get("category", "reasoning")

        # Instruction following — uses IFEval CHECKERS (all must pass for correctness)
        if category == "instruction_following":
            prompt = sample.get("prompt", sample.get("question", ""))
            instruction_ids = sample.get("instruction_ids", [])
            kwargs_list = sample.get("kwargs", [])
        # Math — extract integer via AIME answer parser, compare to expected value
        elif category == "math":
            prompt = f"{sample['question']}\n\nThink step by step, then provide your final answer as 'Answer: N' where N is the integer."
        # Coding — Docker sandbox with unittest suite injected after model-generated code
        elif category == "coding":
            code_prompt = sample.get("prompt", "")
            test_suite = sample.get("test", "")
            entry_point = sample.get("entry_point", "")
            prompt = code_prompt
        # MCQ (language, data, reasoning) — regex letter extraction from options
        else:
            options = sample.get("options", [])
            prompt = f"{sample['question']}\n\nOptions:\n"
            for letter, opt in zip("ABCDEFGHIJ", options):
                prompt += f"  {letter}. {opt}\n"
            prompt += "\nAnswer with only the letter of the correct option."

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        answer_content = gen.get("answer_content", "").strip()
        raw_response = gen.get("raw_response", "")

        correct = False
        error_message = None
        extracted = answer_content

        if category == "instruction_following":
            response = answer_content or raw_response
            failed = []
            for i, instr_id in enumerate(instruction_ids):
                checker = CHECKERS.get(instr_id)
                if checker is None:
                    failed.append(f"{instr_id}:unknown_checker")
                    continue
                kw = dict(kwargs_list[i]) if i < len(kwargs_list) else {}
                if instr_id == "combination:repeat_prompt":
                    kw["prompt"] = prompt
                try:
                    if not checker(response, kw):
                        failed.append(instr_id)
                except Exception as e:
                    failed.append(f"{instr_id}:{e}")
            correct = len(failed) == 0
            error_message = "; ".join(failed) if failed else None
            extracted = response

        elif category == "math":
            val = extract_aime_answer(answer_content)
            expected = sample["answer"]
            correct = val == expected
            if not correct:
                error_message = f"Expected {expected}, got {val}"

        elif category == "coding":
            if not test_suite or not test_suite.strip():
                return {
                    "prompt": prompt,
                    "raw_response": raw_response,
                    "extracted_code": "",
                    "correct": False,
                    "error_message": "No test suite available",
                    "elapsed_time": gen["elapsed_time"],
                    "tps": gen["tps"],
                    "ttft": gen["ttft"],
                    "thinking_tokens": gen["thinking_tokens"],
                    "response_tokens": gen["response_tokens"]
                }
            from backend.sandbox.docker_executor import DockerExecutor
            if self._coding_executor is None:
                self._coding_executor = DockerExecutor()
                self.requires_docker = True
            executor = self._coding_executor
            if executor.is_available():
                response_text = answer_content or raw_response
                code_blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
                code = code_blocks[0].strip() if code_blocks else response_text
                test_script = f"{code}\n\n{test_suite}\n\nif __name__ == '__main__':\n    unittest.main(exit=True)\n"
                try:
                    res = executor.execute_python_code(test_script, timeout=10.0, benchmark_name="livebench")
                    correct = res["success"]
                    if not correct:
                        error_message = res.get("error") or res.get("stderr")
                except Exception as e:
                    error_message = f"Docker execution error: {e}"
                extracted = response_text
            else:
                error_message = "Docker unavailable for coding task"
                extracted = answer_content or raw_response

        else:
            answer_upper = answer_content.upper()
            opts = re.findall(r'\b([A-J])\b', answer_upper)
            answer = opts[-1] if opts else None
            correct = answer == sample.get("answer", "")
            if not correct:
                error_message = f"Expected {sample.get('answer', '')}, got {answer}"
            extracted = answer_content

        return {
            "prompt": prompt,
            "raw_response": raw_response,
            "extracted_code": extracted,
            "correct": correct,
            "error_message": error_message,
            "elapsed_time": gen["elapsed_time"],
            "tps": gen["tps"],
            "ttft": gen["ttft"],
            "thinking_tokens": gen["thinking_tokens"],
            "response_tokens": gen["response_tokens"]
        }

    def cleanup(self) -> None:
        if self._coding_executor:
            self._coding_executor.cleanup()
