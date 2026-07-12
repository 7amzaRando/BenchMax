import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.benchmarks.scoring import get_scorer
from backend.lm_studio.client import LMStudioClient
from backend.database import Run, Result

logger = logging.getLogger(__name__)


class BenchMaxTectonicBenchmark(BaseBenchmark):
    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)
        self.quick_test = quick_test

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "tectonic_mini.json" if self.quick_test else "tectonic_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            self.dataset_path = resolve_data_file(__file__, "tectonic_mini.json")
            if self.dataset_path:
                logger.warning("Full Tectonic dataset not found, falling back to mini dataset")
        if not self.dataset_path:
            raise FileNotFoundError("Neither full nor mini dataset found for BenchMax Tectonic")
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        gen = await self.client.generate_completion(
            prompt=sample.get("prompt", ""),
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )
        raw = gen.get("raw_response", "")
        qtype = sample.get("type", "free_form")
        answer = sample.get("answer", "")
        if qtype == "code":
            ans = answer.strip()
            answer = ans.split("(")[0].strip() if "(" in ans else (ans.split()[0] if ans else "")
        scorer = get_scorer(qtype)
        correct, error_msg = scorer(raw, answer)

        return {
            "prompt": sample.get("prompt", ""),
            "raw_response": raw,
            "extracted_code": raw,
            "correct": correct,
            "error_message": error_msg or None,
            "elapsed_time": gen.get("elapsed_time", 0.0),
            "tps": gen.get("tps", 0.0),
            "ttft": gen.get("ttft", 0.0),
            "thinking_tokens": gen.get("thinking_tokens", 0),
            "response_tokens": gen.get("response_tokens", 0),
        }

    async def run_evaluation(self, run_id: int, params: Dict[str, Any]) -> None:
        # Delegate to parent for standard evaluation loop with halt/pause detection
        await super().run_evaluation(run_id, params)

        run = self.db.query(Run).filter(Run.id == run_id).first()
        if run and run.status in ("COMPLETED", "FAILED"):
            result_rows = self.db.query(Result).filter(
                Result.run_id == run_id
            ).all()

            task_to_cat: Dict[str, str] = {}
            for s in self.load_dataset():
                task_to_cat[s["task_id"]] = s.get("category", "Knowledge")

            categories = ["Code", "Logic/Reasoning", "Instruction Following", "Knowledge", "Tool Calling"]
            cat_results: Dict[str, list] = {c: [] for c in categories}

            for r in result_rows:
                if r.task_id in ("personal_bms_score", "tectonic_bms_score"):
                    continue
                cat = task_to_cat.get(r.task_id, "Knowledge")
                if cat in cat_results:
                    cat_results[cat].append(r.correct)

            category_scores = {}
            for cat in categories:
                scores = cat_results.get(cat, [])
                cat_score = (sum(scores) / len(scores) * 100) if scores else 0.0
                category_scores[cat] = round(cat_score, 1)

            tectonic_metrics = {"category_scores": category_scores}
            run_params = run.get_parameters()
            run_params["_tectonic_metrics"] = tectonic_metrics
            run.set_parameters(run_params)
            self.db.commit()

            logger.info(f"BenchMax Tectonic completed — {run.total_samples} samples")
