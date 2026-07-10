import json
import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
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
        self.quick_test = quick_test

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "personal_mini.json" if self.quick_test else "personal_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            self.dataset_path = resolve_data_file(__file__, "personal_mini.json")
            if self.dataset_path:
                logger.warning("Full Personal dataset not found, falling back to mini dataset")
        if not self.dataset_path:
            raise FileNotFoundError("Neither full nor mini dataset found for BenchMax Personal")
        return self._load_json_cached(self.dataset_path)

    def _score_mcq(self, response: str, answer: str) -> bool:
        matches = re.findall(r'(?<!\w)([A-D])(?!\w)', response)
        if not matches:
            return False
        return matches[-1] == answer

    def _score_code(self, response: str, answer: str) -> bool:
        if not re.search(r'\bdef\s+\w+\s*\(', response):
            return False
        if not answer.strip():
            return False
        keywords = [k.strip().lower() for k in answer.replace(",", " ").split() if len(k.strip()) > 2]
        if not keywords:
            return False
        resp_lower = response.lower()
        return sum(1 for k in keywords if k in resp_lower) >= len(keywords) * 0.5

    def _score_free_form(self, response: str, answer: str) -> bool:
        if not answer.strip():
            return False
        keywords = [k.strip().lower() for k in answer.replace(",", " ").split() if len(k.strip()) > 2]
        if not keywords:
            return False
        resp_lower = response.lower()
        return sum(1 for k in keywords if k in resp_lower) >= len(keywords) * 0.5

    def _score_function_call(self, response: str, answer: str) -> bool:
        return bool(re.search(r'\b' + re.escape(answer) + r'\b', response, re.IGNORECASE))

    def _score_safety(self, response: str, _answer: str) -> bool:
        refusal = re.search(r'(sorry|cannot|i can\'t|unable to|not appropriate|decline)', response.lower())
        return refusal is not None

    def _get_scorer(self, qtype: str):
        return {
            "mcq": self._score_mcq,
            "code": self._score_code,
            "free_form": self._score_free_form,
            "function_call": self._score_function_call,
            "safety": self._score_safety,
        }.get(qtype, self._score_free_form)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        gen = await self.client.generate_completion(
            prompt=sample["prompt"],
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )
        raw = gen.get("raw_response", "")
        qtype = sample.get("type", "free_form")
        scorer = self._get_scorer(qtype)
        correct = scorer(raw, sample.get("answer", ""))

        return {
            "prompt": sample["prompt"],
            "raw_response": raw,
            "extracted_code": raw,
            "correct": correct,
            "error_message": None,
            "elapsed_time": gen.get("elapsed_time", 0.0),
            "tps": gen.get("tps", 0.0),
            "ttft": gen.get("ttft", 0.0),
            "thinking_tokens": gen.get("thinking_tokens", 0),
            "response_tokens": gen.get("response_tokens", 0),
        }

    async def run_evaluation(self, run_id: int, params: Dict[str, Any]) -> None:
        # Delegate to parent for standard evaluation loop with halt/pause detection
        await super().run_evaluation(run_id, params)

        # Compute dimension scores and BMS from results already in DB
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if run and run.status in ("COMPLETED", "FAILED"):
            result_rows = self.db.query(Result).filter(
                Result.run_id == run_id
            ).all()
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
