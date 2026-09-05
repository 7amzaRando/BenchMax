import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.scoring import score_sample
from backend.lm_studio.client import LMStudioClient
from backend.database import Run, Result

logger = logging.getLogger(__name__)


class BenchMaxTectonicBenchmark(BaseBenchmark):
    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("tectonic_full.json")
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

            task_to_cat: Dict[str, str] = {}
            for s in self.load_dataset():
                task_to_cat[s["task_id"]] = s.get("category", "Knowledge")

            # Fixed: dataset uses "Coding" not "Code"; sort for display
            categories = sorted(["Coding", "Logic/Reasoning", "Instruction Following", "Knowledge", "Tool Calling"])
            cat_results: Dict[str, list] = {c: [] for c in categories}

            for r in result_rows:
                if r.task_id in ("personal_bms_score", "tectonic_bms_score"):
                    continue
                cat = task_to_cat.get(r.task_id, "Knowledge")
                if cat in cat_results:
                    cat_results[cat].append(r.correct)

            category_scores = {}
            for cat in sorted(categories):
                scores = cat_results.get(cat, [])
                cat_score = (sum(scores) / len(scores) * 100) if scores else 0.0
                category_scores[cat] = round(cat_score, 1)
            # Ensure sorted for later display
            category_scores = dict(sorted(category_scores.items()))

            tectonic_metrics = {"category_scores": category_scores}
            run_params = run.get_parameters()
            run_params["_tectonic_metrics"] = tectonic_metrics
            run.set_parameters(run_params)
            self.db.commit()

            logger.info(f"BenchMax Tectonic completed — {run.total_samples} samples")
