import logging
from typing import Dict, Any

from backend.benchmarks.scorer_base import ScorerBenchmark
from backend.database import Run

logger = logging.getLogger(__name__)

DIMENSIONS = [
    {"name": "Code",      "weight": 20},
    {"name": "Knowledge", "weight": 15},
    {"name": "Math",      "weight": 15},
    {"name": "Logic",     "weight": 10},
]
CATEGORY_MAP = {d["name"]: d for d in DIMENSIONS}


class BenchMaxLiteBenchmark(ScorerBenchmark):
    dataset_file = "lite_full.json"

    async def run_evaluation(self, run_id: int, params: Dict[str, Any]) -> None:
        await super().run_evaluation(run_id, params)
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if run:
            run_params = run.get_parameters()
            metrics = run_params.get("_lite_metrics")
            if metrics:
                logger.info(f"BenchMax Lite completed — BMS: {metrics.get('benchmax_score')}")
