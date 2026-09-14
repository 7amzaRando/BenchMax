import logging
import string as string_module
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.scoring import _expand_valid_letters, score_mcq

logger = logging.getLogger(__name__)


class GenericMCQBenchmark(BaseBenchmark):
    """Base class for multiple-choice question benchmarks.
    Subclasses only need to set: dataset_file, valid_letters, fetch_hint."""

    dataset_file: str = ""
    valid_letters: str = "A-J"
    fetch_hint: str = ""

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset(self.dataset_file, fetch_hint=self.fetch_hint)
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        options = sample.get("options", [])
        prompt = f"{sample.get('question', '')}\n\nOptions:\n"
        for letter, opt in zip(self.valid_letters, options):
            prompt += f"  {letter}. {opt}\n"
        prompt += "\nAnswer with only the letter of the correct option."

        gen = await self._generate(prompt, params, model_name)

        ac = gen.get("answer_content", "").strip()
        answer_content = (ac if ac else gen.get("raw_response", "")).strip()
        # Option universe = letters actually shown (options count), capped by
        # the benchmark's valid_letters. A stray letter from prose outside the
        # shown options can no longer count as (or spoil) the answer.
        shown = [string_module.ascii_uppercase[i] for i in range(len(options))]
        allowed = _expand_valid_letters(self.valid_letters)
        universe = "".join(L for L in shown if L in allowed) or self.valid_letters
        correct, err = score_mcq(answer_content, sample.get("answer", ""),
                                 universe, single_answer=True)

        # Store category for per-category chart (sorted display via operations.py)
        cat = sample.get("category") or sample.get("topic") or sample.get("domain") or sample.get("subject") or "unknown"
        return self._result(
            prompt, gen,
            extracted_code=answer_content,
            correct=correct,
            error_message=None if correct else err,
            scoring_details={"category": cat},
        )
