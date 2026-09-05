import json
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.scoring import score_sample
from backend.lm_studio.client import LMStudioClient
from backend.database import Run, Result

logger = logging.getLogger(__name__)

DIMENSIONS = [
    {"name": "Code",              "weight": 25},
    {"name": "Knowledge",         "weight": 15},
    {"name": "Instruction Following", "weight": 15},
    {"name": "Math",              "weight": 25},
    {"name": "Logic",             "weight": 20},
]
CATEGORY_MAP = {d["name"]: d for d in DIMENSIONS}


class BenchMaxPersonalBenchmark(BaseBenchmark):
    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("personal_full.json")
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

    async def run_evaluation(self, run_id: int, params: Dict[str, Any]) -> None:
        await super().run_evaluation(run_id, params)

        run = self.db.query(Run).filter(Run.id == run_id).first()
        if run and run.status in ("COMPLETED", "FAILED"):
            result_rows = self.db.query(Result).filter(Result.run_id == run_id).all()
            dim_results: Dict[str, list] = {d["name"]: [] for d in DIMENSIONS}
            task_to_cat: Dict[str, str] = {}
            for s in self.load_dataset():
                task_to_cat[s["task_id"]] = s.get("category", "Knowledge")
            for r in result_rows:
                cat = task_to_cat.get(r.task_id, "Knowledge")
                dim_results.setdefault(cat, []).append(r.correct)

            dimension_scores = {}
            for d in DIMENSIONS:
                scores = dim_results.get(d["name"], [])
                dim_score = (sum(scores) / len(scores) * 100) if scores else 0.0
                dimension_scores[d["name"]] = round(dim_score, 1)
            # Sort for display (keep original DIMENSIONS order for BMS calculation)
            dimension_scores = dict(sorted(dimension_scores.items()))

            bms = round(sum(
                dimension_scores.get(d["name"], 0.0) * d["weight"] / 100.0
                for d in DIMENSIONS
            ), 1)

            existing_bms = self.db.query(Result).filter(
                Result.run_id == run_id, Result.task_id == "personal_bms_score"
            ).first()
            if existing_bms:
                self.db.delete(existing_bms)
                self.db.flush()

            final_data = {
                "benchmax_score": bms,
                "dimensions": dimension_scores,
                "weights": {d["name"]: d["weight"] for d in DIMENSIONS},
            }

            bms_result = Result(
                run_id=run_id,
                task_id="personal_bms_score",
                prompt="BenchMax Personal — Final BMS Score",
                raw_response=json.dumps(dimension_scores),
                extracted_code=json.dumps(final_data),
                correct=True,
                error_message=None,
                elapsed_time=0.0,
                tps=0.0,
                ttft=0.0,
                thinking_tokens=0,
                response_tokens=0,
            )
            self.db.add(bms_result)

            run_params = run.get_parameters()
            run_params["_personal_metrics"] = final_data
            run.set_parameters(run_params)

            self.db.commit()
            logger.info(f"BenchMax Personal completed — BMS: {bms}")
