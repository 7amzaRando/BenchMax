import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.scoring import score_sample
from backend.lm_studio.client import LMStudioClient

logger = logging.getLogger(__name__)


class ScorerBenchmark(BaseBenchmark):
    """Base class for benchmarks that use get_scorer() for evaluation.
    Subclasses only need to set: dataset_file."""

    dataset_file: str = ""

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset(self.dataset_file)
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        gen = await self._generate(sample.get("prompt", ""), params, model_name)
        raw = gen.get("raw_response", "")
        correct, error_msg = score_sample(raw, sample)
        cat = sample.get("category", "unknown")
        return self._result(
            sample.get("prompt", ""), gen,
            extracted_code=raw,
            correct=correct,
            error_message=error_msg or None,
            scoring_details={"category": cat},
        )
