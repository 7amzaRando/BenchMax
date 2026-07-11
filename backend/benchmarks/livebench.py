import re
import logging
from typing import Dict, Any, List

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.benchmarks.aime import extract_aime_answer
from backend.benchmarks.ifeval_official import instructions_registry

logger = logging.getLogger(__name__)

class LiveBenchBenchmark(BaseBenchmark):
    """
    6-category meta-benchmark:
    - MCQ (regex A-D), math (extract number via AIME answer parser), code (safe_executor),
      language (string match), data (string match), instruction (rule-based IFEval CHECKERS).
    """
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

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
        # Coding — safe_executor with unittest suite injected after model-generated code
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
            is_following = []
            for i, instr_id in enumerate(instruction_ids):
                cls = instructions_registry.INSTRUCTION_DICT.get(instr_id)
                if cls is None:
                    is_following.append(False)
                    continue
                try:
                    instruction = cls(instr_id)
                    accepted = instruction.get_instruction_args_keys()
                    kw = dict(kwargs_list[i]) if i < len(kwargs_list) else {}
                    kw = {k: v for k, v in kw.items() if k in accepted and v is not None}
                    instruction.build_description(**kw)
                    args = instruction.get_instruction_args()
                    if args and "prompt" in args:
                        instruction.build_description(prompt=prompt)
                    if response.strip() and instruction.check_following(response):
                        is_following.append(True)
                    else:
                        is_following.append(False)
                except Exception as e:
                    logger.warning("LiveBench IFEval %s failed: %s", instr_id, e)
                    is_following.append(False)
            failed = [instr_id for instr_id, ok in zip(instruction_ids, is_following) if not ok]
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
            from backend.sandbox.safe_executor import check_correctness_humaneval
            response_text = answer_content or raw_response
            code_blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
            code = code_blocks[0].strip() if code_blocks else response_text
            entry_point = sample.get("entry_point", "solution")
            prompt_text = sample.get("prompt", "")
            try:
                result = check_correctness_humaneval(
                    entry_point=entry_point,
                    prompt=prompt_text,
                    completion=code,
                    test_suite=test_suite,
                    timeout=10.0,
                )
                correct = result["passed"]
                if not correct:
                    error_message = result["result"]
            except Exception as e:
                error_message = f"Execution error: {e}"
            extracted = response_text

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
        pass
