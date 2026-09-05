import ast
import re
import logging
from typing import Dict, Any, List, Optional

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.benchmarks.aime import extract_aime_answer
from backend.benchmarks.ifeval_official import instructions_registry

logger = logging.getLogger(__name__)

def _extract_answer_numbers(text: str) -> Optional[List[int]]:
    """Extract the integer list from the model's final 'Answer:' line.

    Falls back to all integers in the response when no 'Answer:' line exists.
    """
    m = re.search(r"[Aa]nswer\s*:\s*(.*)", text)
    if m:
        nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
        if nums:
            return nums
    nums = [int(x) for x in re.findall(r"\d+", text)]
    return nums or None

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

    @staticmethod
    def _parse_question_list(question: Any) -> List[str]:
        """LiveBench stores `question` as a stringified Python list of prompt chunks."""
        if isinstance(question, list):
            return [str(q) for q in question]
        if isinstance(question, str):
            stripped = question.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = ast.literal_eval(stripped)
                    if isinstance(parsed, list):
                        return [str(p) for p in parsed]
                except (ValueError, SyntaxError):
                    pass
        return [str(question)]

    @classmethod
    def _parse_question_text(cls, question: Any) -> str:
        return "\n\n".join(cls._parse_question_list(question))

    @staticmethod
    def _parse_kwargs(item: Any) -> Dict:
        """Parse an IFEval kwargs entry (dict or stringified dict with numpy array reprs)."""
        if isinstance(item, dict):
            kwd = dict(item)
        elif isinstance(item, str):
            cleaned = re.sub(r"array\((.*?),\s*dtype=object\)", r"\1", item)
            try:
                parsed = ast.literal_eval(cleaned)
            except (ValueError, SyntaxError):
                parsed = None
            kwd = dict(parsed) if isinstance(parsed, dict) else {}
        else:
            kwd = {}
        # Normalize integral floats (3.0 -> 3) so built descriptions match prompt text
        return {
            k: (int(v) if isinstance(v, float) and v.is_integer() else v)
            for k, v in kwd.items()
        }

    @staticmethod
    def _infer_instruction_ids(instruction_texts: List[str], kwargs_list: Any) -> Dict[str, Dict]:
        """Infer applicable IFEval instructions from the prompt when instruction_ids is empty.

        For each kwargs entry, find every instruction class whose built description
        appears in the prompt text. First match per instruction id wins.
        Returns {instruction_id: filtered_kwargs}.
        """
        matched: Dict[str, Dict] = {}
        for kw_item in kwargs_list or []:
            kwd = LiveBenchBenchmark._parse_kwargs(kw_item)
            for iid, cls in instructions_registry.INSTRUCTION_DICT.items():
                if iid in matched:
                    continue
                try:
                    inst = cls(iid)
                    accepted = set(inst.get_instruction_args_keys())
                    kf = {k: v for k, v in kwd.items() if k in accepted and v is not None}
                    desc = inst.build_description(**kf)
                    if desc and any(desc in t for t in instruction_texts):
                        matched[iid] = kf
                except Exception:
                    continue
        return matched

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        category = sample.get("category", "reasoning")

        questions = self._parse_question_list(sample.get("question", ""))
        question_text = "\n\n".join(questions)

        # Instruction following — uses IFEval CHECKERS (all must pass for correctness)
        if category == "instruction_following":
            prompt = question_text
            instruction_ids = sample.get("instruction_ids", []) or []
            kwargs_list = sample.get("kwargs", [])
        # Math — extract integer via AIME answer parser, compare to expected value
        elif category == "math":
            prompt = f"{question_text}\n\nThink step by step, then provide your final answer as 'Answer: N' where N is the integer."
        # Coding — safe_executor with unittest suite injected after model-generated code
        elif category == "coding":
            code_prompt = question_text
            test_suite = sample.get("test", "") or ""
            entry_point = sample.get("entry_point", "") or "solution"
            prompt = code_prompt
        # MCQ (language, data, reasoning) — regex letter extraction from options
        else:
            options = sample.get("options", [])
            prompt = f"{question_text}\n\nOptions:\n"
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
            if instruction_ids:
                is_following = []
                for i, instr_id in enumerate(instruction_ids):
                    cls = instructions_registry.INSTRUCTION_DICT.get(instr_id)
                    if cls is None:
                        is_following.append(False)
                        continue
                    try:
                        instruction = cls(instr_id)
                        accepted = instruction.get_instruction_args_keys()
                        kw = self._parse_kwargs(kwargs_list[i]) if i < len(kwargs_list) else {}
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
            else:
                matched = self._infer_instruction_ids(questions, kwargs_list)
                if not matched:
                    logger.warning(
                        "LiveBench %s: no IFEval instructions inferable from prompt, "
                        "scoring sample as failed",
                        sample.get("task_id", "unknown"),
                    )
                    error_message = "No IFEval instructions inferable from prompt"
                is_following = []
                for instr_id, kf in matched.items():
                    try:
                        instruction = instructions_registry.INSTRUCTION_DICT[instr_id](instr_id)
                        instruction.build_description(**kf)
                        if response.strip() and instruction.check_following(response):
                            is_following.append(True)
                        else:
                            is_following.append(False)
                    except Exception as e:
                        logger.warning("LiveBench IFEval %s check failed: %s", instr_id, e)
                        is_following.append(False)
                failed = [instr_id for instr_id, ok in zip(matched.keys(), is_following) if not ok]
                correct = len(failed) == 0 and len(matched) > 0
                if failed:
                    error_message = "; ".join(failed)
                elif matched:
                    error_message = None
            extracted = response

        elif category == "math":
            expected_raw = str(sample.get("answer", "")).strip()
            expected_nums = [int(x) for x in re.findall(r"\d+", expected_raw)]
            actual_nums = _extract_answer_numbers(answer_content)
            correct = bool(expected_nums) and actual_nums is not None and actual_nums == expected_nums
            if not correct:
                val = extract_aime_answer(answer_content)
                expected_single = expected_nums[-1] if expected_nums else None
                correct = expected_single is not None and val == expected_single
                if not correct:
                    error_message = f"Expected {expected_raw}, got {actual_nums if actual_nums is not None else val}"
            extracted = answer_content

        elif category == "coding":
            response_text = answer_content or raw_response
            code_blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
            code = code_blocks[0].strip() if code_blocks else response_text.strip()
            extracted = code
            if not code:
                error_message = "No code extracted from model response"
            elif not test_suite or not test_suite.strip():
                error_message = "No test suite available for this sample"
            else:
                from backend.sandbox.safe_executor import check_correctness_humaneval
                try:
                    result = check_correctness_humaneval(
                        entry_point=entry_point or "solution",
                        prompt=code_prompt,
                        completion=code,
                        test_suite=test_suite,
                        timeout=10.0,
                    )
                    correct = result["passed"]
                    if not correct:
                        error_message = result["result"]
                except Exception as e:
                    error_message = f"Execution error: {e}"

        else:
            answer_upper = answer_content.upper()
            opts = re.findall(r'\b([A-D])\b', answer_upper)
            answer = opts[-1] if opts else None
            correct = answer == sample.get("answer", "")
            if not correct:
                error_message = f"Expected {sample.get('answer', '')}, got {answer}"
            extracted = answer_content

        return self._result(
            prompt, gen,
            extracted_code=extracted,
            correct=correct,
            error_message=error_message,
            scoring_details={"category": category},
        )
