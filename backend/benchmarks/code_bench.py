import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.lm_studio.client import LMStudioClient
from backend.database import Run, Result

logger = logging.getLogger(__name__)


class BenchMaxCodeBenchmark(BaseBenchmark):
    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        super().__init__(db, client, quick_test)
        self.quick_test = quick_test

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "code_mini.json" if self.quick_test else "code_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            self.dataset_path = resolve_data_file(__file__, "code_mini.json")
            if self.dataset_path:
                logger.warning("Full Code dataset not found, falling back to mini dataset")
        if not self.dataset_path:
            raise FileNotFoundError("Neither full nor mini dataset found for BenchMax Code")
        return self._load_json_cached(self.dataset_path)

    def _score_code(self, response: str, answer: str) -> bool:
        ans = answer.strip()
        func_name = ans.split("(")[0].strip() if "(" in ans else (ans.split()[0] if ans else "")
        if not func_name:
            return False
        return bool(re.search(r'def\s+' + re.escape(func_name) + r'\s*\(', response))

    def _score_mcq(self, response: str, answer: str) -> bool:
        matches = re.findall(r'(?<!\w)([A-Z])(?!\w)', response)
        if not matches:
            return False
        return matches[-1] == answer

    def _score_exact(self, response: str, answer: str) -> bool:
        return answer.strip().lower() in response.lower()

    def _get_scorer(self, qtype: str):
        return {
            "mcq": self._score_mcq,
            "code": self._score_code,
            "exact": self._score_exact,
        }.get(qtype, self._score_code)

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
            logger.info(f"BenchMax Code completed — {run.total_samples} samples")
