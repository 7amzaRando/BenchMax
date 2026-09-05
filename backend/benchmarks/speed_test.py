import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark
from backend.lm_studio.client import LMStudioClient
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class WritingSpeedTestBenchmark(BaseBenchmark):
    """Writing & Creative Writing speed benchmark (5 prompts, ~300 tokens each).

    Tests creative text generation including RP dialogue, short stories,
    descriptive passages, and poetry. No code extraction — correct is always True.
    """

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("writing_speed_test_full.json")
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample.get("prompt", "")
        category = sample.get("category", "short")

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.7),
            max_completion_tokens=sample.get("target_tokens", 300),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        raw_response = gen.get("raw_response", "")
        total_tokens = (gen.get("thinking_tokens") or 0) + (gen.get("response_tokens") or 0)
        correct = bool(raw_response.strip())

        return self._result(
            prompt, gen,
            extracted_code="",
            correct=correct,
            error_message=None if correct else "Empty response",
            scoring_details={
                "category": category,
                "target_tokens": sample.get("target_tokens", 300),
                "generated_tokens": total_tokens,
            },
        )


class CodingSpeedTestBenchmark(BaseBenchmark):
    """Coding speed benchmark (5 prompts, ~300 tokens each).

    Tests raw code generation speed — functions, scripts, regex patterns,
    and data structures. correct is always True.
    """

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("coding_speed_test_full.json")
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample.get("prompt", "")
        category = sample.get("category", "short")

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.7),
            max_completion_tokens=sample.get("target_tokens", 300),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        raw_response = gen.get("raw_response", "")
        total_tokens = (gen.get("thinking_tokens") or 0) + (gen.get("response_tokens") or 0)
        correct = bool(raw_response.strip())

        return self._result(
            prompt, gen,
            extracted_code="",
            correct=correct,
            error_message=None if correct else "Empty response",
            scoring_details={
                "category": category,
                "target_tokens": sample.get("target_tokens", 300),
                "generated_tokens": total_tokens,
            },
        )
