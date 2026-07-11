import json
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PROMPT_CATEGORIES = {
    "short": "Short (~300 tokens)",
    "medium": "Medium (~300 tokens)",
}


class WritingSpeedTestBenchmark(BaseBenchmark):
    """Writing & Creative Writing speed benchmark (5 prompts, ~300 tokens each).

    Tests creative text generation including RP dialogue, short stories,
    descriptive passages, and poetry. No code extraction — correct is always True.
    """

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "writing_speed_test_mini.json" if self.quick_test else "writing_speed_test_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            self.dataset_path = resolve_data_file(__file__, "writing_speed_test_mini.json")
            if self.dataset_path:
                logger.warning("Full writing speed test dataset not found, falling back to mini dataset")
        if not self.dataset_path:
            raise FileNotFoundError("Neither full nor mini dataset found for Writing Speed Test")
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample["prompt"]
        category = sample.get("category", "short")

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.7),
            max_completion_tokens=sample.get("target_tokens", 300),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        total_tokens = (gen.get("thinking_tokens") or 0) + (gen.get("response_tokens") or 0)

        return {
            "prompt": prompt,
            "raw_response": gen.get("raw_response", ""),
            "extracted_code": "",
            "correct": True,
            "error_message": None,
            "elapsed_time": gen.get("elapsed_time", 0.0),
            "tps": gen.get("tps", 0.0),
            "ttft": gen.get("ttft", 0.0),
            "thinking_tokens": gen.get("thinking_tokens", 0),
            "response_tokens": gen.get("response_tokens", 0),
            "scoring_details": json.dumps({
                "category": category,
                "target_tokens": sample.get("target_tokens", 300),
                "generated_tokens": total_tokens,
            }),
        }


class CodingSpeedTestBenchmark(BaseBenchmark):
    """Coding speed benchmark (5 prompts, ~300 tokens each).

    Tests raw code generation speed — functions, scripts, regex patterns,
    and data structures. correct is always True.
    """

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "coding_speed_test_mini.json" if self.quick_test else "coding_speed_test_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            self.dataset_path = resolve_data_file(__file__, "coding_speed_test_mini.json")
            if self.dataset_path:
                logger.warning("Full coding speed test dataset not found, falling back to mini dataset")
        if not self.dataset_path:
            raise FileNotFoundError("Neither full nor mini dataset found for Coding Speed Test")
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample["prompt"]
        category = sample.get("category", "short")

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.7),
            max_completion_tokens=sample.get("target_tokens", 300),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        total_tokens = (gen.get("thinking_tokens") or 0) + (gen.get("response_tokens") or 0)

        return {
            "prompt": prompt,
            "raw_response": gen.get("raw_response", ""),
            "extracted_code": "",
            "correct": True,
            "error_message": None,
            "elapsed_time": gen.get("elapsed_time", 0.0),
            "tps": gen.get("tps", 0.0),
            "ttft": gen.get("ttft", 0.0),
            "thinking_tokens": gen.get("thinking_tokens", 0),
            "response_tokens": gen.get("response_tokens", 0),
            "scoring_details": json.dumps({
                "category": category,
                "target_tokens": sample.get("target_tokens", 300),
                "generated_tokens": total_tokens,
            }),
        }
