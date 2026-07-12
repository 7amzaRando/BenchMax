import re
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file

logger = logging.getLogger(__name__)

class MMLUProBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "mmlu_pro_mini.json" if self.quick_test else "mmlu_pro_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            raise FileNotFoundError(
                "MMLU-Pro dataset not found. "
                "Run 'scripts/fetch_mmlu_pro.py' to download it."
            )
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        options = sample.get("options", [])
        prompt = f"{sample.get('question', '')}\n\nOptions:\n"
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

        ac = gen.get("answer_content", "").strip()
        answer_content = (ac if ac else gen.get("raw_response", "")).strip().upper()
        extracted = re.findall(r'\b([A-J])\b', answer_content)
        answer = extracted[-1] if extracted else None
        correct = answer == sample.get("answer", "")

        return {
            "prompt": prompt,
            "raw_response": gen["raw_response"],
            "extracted_code": answer_content,
            "correct": correct,
            "error_message": None if correct else f"Expected {sample.get('answer', '')}, got {answer}",
            "elapsed_time": gen["elapsed_time"],
            "tps": gen["tps"],
            "ttft": gen["ttft"],
            "thinking_tokens": gen["thinking_tokens"],
            "response_tokens": gen["response_tokens"]
        }
