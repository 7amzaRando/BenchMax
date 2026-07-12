import re
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file

logger = logging.getLogger(__name__)


class TruthfulQABenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "truthfulqa_mini.json" if self.quick_test else "truthfulqa_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            msg = "TruthfulQA dataset not found."
            if not self.quick_test:
                fallback = "truthfulqa_mini.json"
                self.dataset_path = resolve_data_file(__file__, fallback)
                if self.dataset_path:
                    logger.warning("Full TruthfulQA dataset not found, falling back to mini dataset")
            if not self.dataset_path:
                raise FileNotFoundError(msg)
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = (
            f"Question: {sample.get('question', '')}\n\n"
            f"Options:\n"
            f"  A. {sample.get('choice_A', '')}\n"
            f"  B. {sample.get('choice_B', '')}\n\n"
            f"Answer with only the letter of the correct option."
        )

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        answer_content = (gen.get("answer_content") or gen.get("raw_response", "")).strip().upper()
        extracted = re.findall(r'\b([A-B])\b', answer_content)
        answer = extracted[-1] if extracted else None
        correct = answer == sample.get("answer", "")

        return {
            "prompt": prompt,
            "raw_response": gen.get("raw_response", ""),
            "extracted_code": answer_content,
            "correct": correct,
            "error_message": None if correct else f"Expected {sample.get('answer', '')}, got {answer}",
            "elapsed_time": gen.get("elapsed_time", 0.0),
            "tps": gen.get("tps", 0.0),
            "ttft": gen.get("ttft", 0.0),
            "thinking_tokens": gen.get("thinking_tokens", 0),
            "response_tokens": gen.get("response_tokens", 0),
        }
