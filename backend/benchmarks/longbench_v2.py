import re
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4
PROMPT_OVERHEAD_CHARS = 800

class LongBenchV2Benchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("longbench_v2_full.json", fetch_hint="Run 'scripts/fetch_longbench_v2.py' to download it.")
        data = self._load_json_cached(path)
        for item in data:
            if "task_id" not in item:
                item["task_id"] = item.get("_id", "unknown")
        return data

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        sample = dict(sample)  # copy to avoid mutating cached dataset
        max_context_tokens = params.get("max_context_tokens", 128000)
        context = sample.get("context", "")
        max_chars = max(1, max_context_tokens * CHARS_PER_TOKEN - PROMPT_OVERHEAD_CHARS)
        if len(context) > max_chars:
            context = context[:max_chars]

        options_block = "\n".join([
            f"  A. {sample.get('choice_A', '')}",
            f"  B. {sample.get('choice_B', '')}",
            f"  C. {sample.get('choice_C', '')}",
            f"  D. {sample.get('choice_D', '')}",
        ])
        prompt = (
            f"Context: {context}\n\n"
            f"Question: {sample.get('question', '')}\n\n"
            f"Options:\n{options_block}\n\n"
            f"Answer with the letter of the correct option."
        )

        gen = await self._generate(prompt, params, model_name)

        ac = gen.get("answer_content", "").strip()
        answer_content = (ac if ac else gen.get("raw_response", "")).strip().upper()
        extracted = re.findall(r'\b([A-D])\b', answer_content)
        answer = extracted[-1] if extracted else None
        correct = answer == sample.get("answer", "")

        cat = sample.get("domain", "unknown")
        return self._result(
            prompt, gen,
            extracted_code=answer_content,
            correct=correct,
            error_message=None if correct else f"Expected {sample.get('answer', '')}, got {answer}",
            scoring_details={"category": cat, "sub_domain": sample.get("sub_domain", ""), "difficulty": sample.get("difficulty", "")},
        )
