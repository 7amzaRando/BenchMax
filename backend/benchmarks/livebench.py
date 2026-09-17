import ast
import json
import re
import logging
from typing import Dict, Any, List, Optional

from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.aime import extract_aime_answer
from backend.benchmarks.ifeval_official import instructions_registry

logger = logging.getLogger(__name__)

# Display truncation limits for stored error messages (DB size, not grading).
_ERROR_TRUNCATE_CHARS = 1500
_EXEC_ERROR_TRUNCATE_CHARS = 500

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


def _split_list_answer(text: str) -> List[str]:
    """Split a comma/newline-separated answer into normalized parts."""
    cleaned = text.replace(" and ", ",")
    return [p.strip().lower() for p in re.split(r"[,\n]+", cleaned) if p.strip()]


def _extract_answer_parts(text: str) -> List[str]:
    """Extract ordered answer parts from a list-style response.

    Prefers the 'Answer:' line (first line after the marker); falls back to
    the last non-empty line so free-form outputs still grade.
    """
    m = re.search(r"[Aa]nswer\s*:\s*(.+)", text)
    if m:
        first_line = m.group(1).split("\n")[0]
        parts = _split_list_answer(first_line)
        if parts:
            return parts
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
    if lines:
        return _split_list_answer(lines[-1])
    return []


def _extract_json_answer(text: str):
    """Extract a JSON value from a data-analysis response (fence or Answer: or raw)."""
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass
    m = re.search(r"[Aa]nswer\s*:\s*([\s\S]+)", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        return None

class LiveBenchBenchmark(BaseBenchmark):
    """
    6-category meta-benchmark:
    - MCQ (regex A-D), math (extract number via AIME answer parser), code (safe_executor),
      language (string match), data (string match), instruction (rule-based IFEval CHECKERS).
    """
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)
        self._docker_usable_cache: bool | None = None

    def _docker_usable(self) -> bool:
        """Probe once per run whether the Docker sandbox can grade code.

        Result is cached on the instance — one `docker info` + image inspect
        per run, not per coding sample. Any failure (daemon down, image not
        built, docker package missing) means "unusable".
        """
        if self._docker_usable_cache is None:
            try:
                from backend.sandbox.docker_executor import is_sandbox_usable
                self._docker_usable_cache = bool(is_sandbox_usable())
            except Exception:
                self._docker_usable_cache = False
        return self._docker_usable_cache

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset(
            "livebench_full.json", mini_name="livebench_mini.json",
            fetch_hint="Run 'scripts/fetch_livebench.py' to download it.",
        )
        self.dataset_path = path
        return self._load_json_cached(path)

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

    def _build_prompt(self, sample: Dict[str, Any], category: str,
                        questions: List[str], question_text: str):
        """Build the model prompt for a sample.

        Returns (prompt, skip_result): skip_result is a ready-made result
        dict when the sample cannot be graded (coding without Docker), else
        None. Generation is skipped entirely in that case.
        """
        # Instruction following — uses IFEval CHECKERS (all must pass for correctness)
        if category == "instruction_following":
            return question_text, None
        # Math — extract integer via AIME answer parser, compare to expected value
        if category == "math":
            return (
                f"{question_text}\n\nThink step by step, then provide your final "
                f"answer as 'Answer: N' where N is the integer.",
                None,
            )
        # Coding — safe_executor with unittest suite injected after model-generated code
        if category == "coding":
            if not self._docker_usable():
                # Skip BEFORE generation: no LLM time/tokens wasted on a
                # sample that cannot be graded without the Docker sandbox.
                return "", self._result(
                    question_text, {},
                    extracted_code="",
                    correct=False,
                    error_message=(
                        "Skipped: Docker sandbox unavailable (daemon not running or "
                        "benchmax-sandbox image not built) — start Docker Desktop and "
                        "build the image to grade coding questions."
                    ),
                    scoring_details={"category": "coding", "skipped": True,
                                     "skip_reason": "docker_unavailable"},
                )
            return question_text, None
        # Ordered lists (reasoning zebra puzzles, language word lists) —
        # the dataset ships comma-separated answers with no options, so ask
        # for a comma-separated Answer: line and compare ordered parts.
        if category in ("reasoning", "language"):
            return (
                f"{question_text}\n\nRespond with ONLY the comma-separated "
                f"answer values on one line as: Answer: v1, v2, ...",
                None,
            )
        # Data analysis — JSON table output compared structurally.
        if category == "data_analysis":
            return (
                f"{question_text}\n\nRespond with ONLY the result "
                f"(a JSON table), no other text.",
                None,
            )
        # MCQ fallback — regex letter extraction from options
        options = sample.get("options", [])
        prompt = f"{question_text}\n\nOptions:\n"
        for letter, opt in zip("ABCDEFGHIJ", options):
            prompt += f"  {letter}. {opt}\n"
        prompt += "\nAnswer with only the letter of the correct option."
        return prompt, None

    def _check_single_instruction(self, instr_id: str, kw: Dict, response: str,
                                  prompt: str, warn_suffix: str = "") -> bool:
        """Build one IFEval instruction and check it against the response."""
        cls = instructions_registry.INSTRUCTION_DICT.get(instr_id)
        if cls is None:
            return False
        try:
            instruction = cls(instr_id)
            accepted = instruction.get_instruction_args_keys()
            kw = {k: v for k, v in kw.items() if k in accepted and v is not None}
            instruction.build_description(**kw)
            args = instruction.get_instruction_args()
            if args and "prompt" in args:
                instruction.build_description(prompt=prompt)
            return bool(response.strip() and instruction.check_following(response))
        except Exception as e:
            logger.warning("LiveBench IFEval %s%s: %s", instr_id, warn_suffix, e)
            return False

    def _grade_instruction_following(self, sample: Dict[str, Any], prompt: str,
                                     questions: List[str], response: str):
        """Grade via IFEval checkers — all must pass. Returns (correct, error, extracted)."""
        instruction_ids = sample.get("instruction_ids", []) or []
        kwargs_list = sample.get("kwargs", [])
        if instruction_ids:
            is_following = [
                self._check_single_instruction(
                    instr_id,
                    self._parse_kwargs(kwargs_list[i]) if i < len(kwargs_list) else {},
                    response, prompt,
                )
                for i, instr_id in enumerate(instruction_ids)
            ]
            failed = [instr_id for instr_id, ok in zip(instruction_ids, is_following) if not ok]
            return len(failed) == 0, ("; ".join(failed) if failed else None), response
        matched = self._infer_instruction_ids(questions, kwargs_list)
        if not matched:
            logger.warning(
                "LiveBench %s: no IFEval instructions inferable from prompt, "
                "scoring sample as failed",
                sample.get("task_id", "unknown"),
            )
            return False, "No IFEval instructions inferable from prompt", response
        is_following = [
            self._check_single_instruction(instr_id, kf, response, prompt, " check failed")
            for instr_id, kf in matched.items()
        ]
        failed = [instr_id for instr_id, ok in zip(matched.keys(), is_following) if not ok]
        if failed:
            return False, "; ".join(failed), response
        return len(matched) > 0, None, response

    @staticmethod
    def _grade_math(sample: Dict[str, Any], answer_content: str):
        """Grade integer math via Answer:-line parse with AIME fallback."""
        expected_raw = str(sample.get("answer", "")).strip()
        expected_nums = [int(x) for x in re.findall(r"\d+", expected_raw)]
        actual_nums = _extract_answer_numbers(answer_content)
        if bool(expected_nums) and actual_nums is not None and actual_nums == expected_nums:
            return True, None, answer_content
        val = extract_aime_answer(answer_content)
        expected_single = expected_nums[-1] if expected_nums else None
        if expected_single is not None and val == expected_single:
            return True, None, answer_content
        return False, f"Expected {expected_raw}, got {actual_nums if actual_nums is not None else val}", answer_content

    def _grade_coding(self, sample: Dict[str, Any], question_text: str,
                      answer_content: str, raw_response: str, gen: Dict[str, Any]):
        """Grade code via the Docker sandbox. Returns (correct, error, extracted)."""
        test_suite = sample.get("test", "") or ""
        entry_point = sample.get("entry_point", "") or "solution"
        response_text = answer_content or raw_response
        thinking = gen.get("thinking_content", "")
        code_blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
        if not code_blocks and thinking:
            code_blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", thinking, re.DOTALL | re.IGNORECASE)
        code = code_blocks[0].strip() if code_blocks else response_text.strip()
        if not code:
            return False, "No code extracted from model response", code
        if not test_suite or not test_suite.strip():
            return False, (
                "No test suite bundled for this LiveBench coding sample "
                "(upstream hidden tests are not vendored)"
            ), code
        from backend.sandbox.safe_executor import check_correctness_humaneval
        try:
            result = check_correctness_humaneval(
                entry_point=entry_point or "solution",
                prompt=question_text,
                completion=code,
                test_suite=test_suite,
                timeout=10.0,
            )
            if result["passed"]:
                return True, None, code
            return False, result["result"][:_ERROR_TRUNCATE_CHARS], code
        except Exception as e:
            return False, f"Execution error: {str(e)[:_EXEC_ERROR_TRUNCATE_CHARS]}", code

    @staticmethod
    def _grade_list(sample: Dict[str, Any], answer_content: str, raw_response: str):
        """Grade ordered comma-separated lists (reasoning/language)."""
        expected_parts = _split_list_answer(str(sample.get("answer", "")))
        actual_parts = _extract_answer_parts(answer_content or raw_response)
        if bool(expected_parts) and actual_parts == expected_parts:
            return True, None, answer_content
        return False, f"Expected {expected_parts}, got {actual_parts}", answer_content

    @staticmethod
    def _grade_data_analysis(sample: Dict[str, Any], answer_content: str, raw_response: str):
        """Grade JSON table output structurally."""
        try:
            expected_json = json.loads(str(sample.get("answer", "")))
        except (json.JSONDecodeError, ValueError):
            expected_json = None
        actual_json = _extract_json_answer(answer_content or raw_response)
        if expected_json is None:
            return False, "No parseable expected JSON in sample", answer_content
        if actual_json is None:
            return False, "No parseable JSON found in response", answer_content
        if actual_json == expected_json:
            return True, None, answer_content
        return False, "JSON output does not match expected table", answer_content

    @staticmethod
    def _grade_mcq(sample: Dict[str, Any], answer_content: str):
        """Grade MCQ via last A-D letter mention."""
        opts = re.findall(r'\b([A-D])\b', answer_content.upper())
        answer = opts[-1] if opts else None
        if answer == sample.get("answer", ""):
            return True, None, answer_content
        return False, f"Expected {sample.get('answer', '')}, got {answer}", answer_content

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        category = sample.get("category", "reasoning")

        questions = self._parse_question_list(sample.get("question", ""))
        question_text = "\n\n".join(questions)

        prompt, skip_result = self._build_prompt(sample, category, questions, question_text)
        if skip_result is not None:
            return skip_result

        gen = await self._generate(prompt, params, model_name)

        answer_content = gen.get("answer_content", "").strip()
        raw_response = gen.get("raw_response", "")

        if category == "instruction_following":
            response = answer_content or raw_response
            correct, error_message, extracted = self._grade_instruction_following(
                sample, prompt, questions, response)
        elif category == "math":
            correct, error_message, extracted = self._grade_math(sample, answer_content)
        elif category == "coding":
            correct, error_message, extracted = self._grade_coding(
                sample, question_text, answer_content, raw_response, gen)
        elif category in ("reasoning", "language"):
            correct, error_message, extracted = self._grade_list(sample, answer_content, raw_response)
        elif category == "data_analysis":
            correct, error_message, extracted = self._grade_data_analysis(sample, answer_content, raw_response)
        else:
            correct, error_message, extracted = self._grade_mcq(sample, answer_content)

        return self._result(
            prompt, gen,
            extracted_code=extracted,
            correct=correct,
            error_message=error_message,
            scoring_details={"category": category},
        )
