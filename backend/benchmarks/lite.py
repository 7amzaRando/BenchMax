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
    {"name": "Code",      "weight": 20},
    {"name": "Knowledge", "weight": 15},
    {"name": "Math",      "weight": 15},
    {"name": "Logic",     "weight": 10},
]
CATEGORY_MAP = {d["name"]: d for d in DIMENSIONS}


class BenchMaxLiteBenchmark(BaseBenchmark):
    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)
        self.quick_test = quick_test

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "lite_mini.json" if self.quick_test else "lite_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            self.dataset_path = resolve_data_file(__file__, "lite_mini.json")
            if self.dataset_path:
                logger.warning("Full Lite dataset not found, falling back to mini dataset")
        if not self.dataset_path:
            raise FileNotFoundError("Neither full nor mini dataset found for BenchMax Lite")
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

    def _get_scorer(self, qtype: str):
        return {
            "mcq": self._score_mcq,
            "code": self._score_code,
            "free_form": self._score_free_form,
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
        await super().run_evaluation(run_id, params)
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if run:
            run_params = run.get_parameters()
            metrics = run_params.get("_lite_metrics")
            if metrics:
                logger.info(f"BenchMax Lite completed — BMS: {metrics.get('benchmax_score')}")
