import re
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark

logger = logging.getLogger(__name__)


def _normalize_answer(text: str) -> str:
    """Normalize answer for comparison: lowercase, strip articles/punctuation/whitespace."""
    text = text.lower().strip()
    text = re.sub(r'^[\s.,;:!?]+|[\s.,;:!?]+$', '', text)
    text = re.sub(r'\b(a|an|the)\b', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = ' '.join(text.split())
    return text


class LongContextMemoryBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset(
            "long_context_memory_full.json",
            fetch_hint="Run 'scripts/fetch_long_context_memory.py' to download it."
        )
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        context = sample.get("context", "")
        question = sample.get("question", "")

        prompt = (
            f"Read the following conversation carefully and answer the question based on the information discussed.\n\n"
            f"Conversation:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer with a short, direct answer."
        )

        gen = await self._generate(prompt, params, model_name)

        ac = gen.get("answer_content", "").strip()
        response = (ac if ac else gen.get("raw_response", "")).strip()
        expected = sample.get("answer", "")

        norm_response = _normalize_answer(response)
        norm_expected = _normalize_answer(expected)

        correct = (norm_expected == norm_response
                   or (len(norm_expected) > 3 and norm_expected in norm_response)
                   or (len(norm_response) > 3 and norm_response in norm_expected))

        if not correct:
            expected_words = set(norm_expected.split())
            response_words = set(norm_response.split())
            if expected_words and expected_words.issubset(response_words):
                correct = True

        cat = sample.get("category", "unknown")
        return self._result(
            prompt, gen,
            extracted_code=response,
            correct=correct,
            error_message=None if correct else f"Expected '{expected}', got '{response}'",
            scoring_details={"category": cat, "expected": expected, "normalized_expected": norm_expected},
        )
