import json
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.database import Run, Result
from backend.lm_studio.client import LMStudioClient

logger = logging.getLogger(__name__)


def resolve_data_file(caller_file: str, filename: str) -> str | None:
    """Find a data file, searching the standard path + exe fallback paths.

    In PyInstaller bundles, __file__ resolves to a temp directory that only
    contains bundled (mini) datasets. This also searches the exe parent dir,
    grandparent, and cwd for user-installed full datasets.
    """
    base = Path(caller_file).parents[2] / "data"
    p = base / filename
    if p.exists():
        return str(p)
    if getattr(sys, 'frozen', False):
        for candidate in [
            Path(sys.executable).parent / "data",
            Path(sys.executable).parent.parent / "data",
            Path.cwd() / "data",
        ]:
            p = candidate / filename
            if p.exists():
                return str(p)
    return None

class BaseBenchmark(ABC):
    _dataset_cache: Dict[str, Any] = {}

    def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False):
        self.db = db
        self.client = client
        self.quick_test = quick_test

    @abstractmethod
    def load_dataset(self) -> List[Dict[str, Any]]:
        """Loads and returns the dataset as a list of dict objects."""
        pass

    @abstractmethod
    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """
        Runs the LLM generation and sandbox code execution for a single sample.
        Returns a dictionary mapping columns of the Result table.
        """
        pass

    def _load_json_cached(self, path: str) -> Any:
        """Load a JSON file with class-level caching."""
        key = f"{self.__class__.__name__}:{path}"
        if key in self._dataset_cache:
            return self._dataset_cache[key]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._dataset_cache[key] = data
        return data

    def cleanup(self) -> None:
        """Override to release resources after benchmark finishes."""
        pass

    async def run_evaluation(self, run_id: int, params: Dict[str, Any]) -> None:
        """
        Main runner loop. Executes the benchmark sequentially, handles
        database state tracking, and listens for pause/halt commands.
        """
        halt_ev = params.get("_halt_event")

        def _is_halted() -> bool:
            if halt_ev and halt_ev.is_set():
                return True
            return False

        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            logger.error(f"Run ID {run_id} not found in database.")
            return

        run.status = "RUNNING"
        self.db.commit()

        dataset = self.load_dataset()
        run.total_samples = len(dataset)
        self.db.commit()

        start_index = run.current_index
        model_name = run.model_name

        logger.info(f"Starting benchmark {run.benchmark_name} for model {model_name} from index {start_index}/{len(dataset)}")

        _batch_size = 5
        _batch_count = 0
        result_buffer = []

        def _flush_batch(final_index):
            nonlocal _batch_count, result_buffer
            if result_buffer:
                self.db.add_all(result_buffer)
                result_buffer = []
            run.current_index = final_index
            self.db.commit()
            _batch_count = 0

        try:
            for i in range(start_index, len(dataset)):
                if _is_halted():
                    logger.info(f"Benchmark run {run_id} halted via in-memory signal at index {i}.")
                    _flush_batch(i)
                    run.status = "HALTED"
                    self.db.commit()
                    return

                # Check for pause / abort on EVERY iteration (not just batch boundaries),
                # otherwise pause never takes effect for short runs (e.g. mini/quick tests).
                self.db.refresh(run)
                if run.status == "PAUSED":
                    logger.info(f"Benchmark run {run_id} paused at index {i}.")
                    run.current_index = i
                    self.db.commit()
                    return
                elif run.status in ("HALTED", "FAILED"):
                    logger.info(f"Benchmark run {run_id} halted/aborted at index {i}.")
                    return

                sample = dataset[i]

                try:
                    result_data = await self.evaluate_sample(sample, params, model_name)

                    if _is_halted():
                        logger.info(f"Benchmark run {run_id} halted mid-sample at index {i} — discarding result.")
                        _flush_batch(i)
                        run.status = "HALTED"
                        self.db.commit()
                        return

                    rep_detected = getattr(self.client, '_repetition_detected', False)
                    if rep_detected:
                        logger.warning(f"Benchmark run {run_id} — repetition detected at index {i}, sending stop and skipping sample.")
                        await self.client.stop_generation(
                            model_name=model_name,
                            system_prompt=None,
                            temperature=0.0,
                            max_tokens=None,
                        )
                        rep_result = Result(
                            run_id=run_id,
                            task_id=sample.get("task_id", f"sample_{i}"),
                            prompt=result_data.get("prompt"),
                            raw_response=result_data.get("raw_response", ""),
                            extracted_code="",
                            correct=False,
                            error_message="Repetition detected — model output is looping (sample skipped)",
                            elapsed_time=result_data.get("elapsed_time", 0.0),
                            tps=0.0, ttft=0.0,
                            thinking_tokens=0, response_tokens=0,
                        )
                        self.db.add(rep_result)
                        run.current_index = i + 1
                        self.db.commit()
                        continue

                    if result_data.get("stream_timed_out"):
                        if not result_data.get("error_message"):
                            result_data["error_message"] = "Stream timed out — no tokens received for 60s (sample skipped)"
                        result_data["correct"] = False

                    standard_keys = {"prompt", "raw_response", "extracted_code",
                                     "correct", "error_message", "elapsed_time",
                                     "tps", "ttft", "thinking_tokens", "response_tokens",
                                     "thinking_content", "answer_content",
                                     "scoring_details"}
                    extra = {k: v for k, v in result_data.items() if k not in standard_keys}
                    if "scoring_details" in result_data:
                        extra["scoring_details"] = result_data["scoring_details"]
                    result_record = Result(
                        run_id=run_id,
                        task_id=sample.get("task_id", f"sample_{i}"),
                        prompt=result_data.get("prompt"),
                        raw_response=result_data.get("raw_response"),
                        extracted_code=result_data.get("extracted_code"),
                        correct=result_data.get("correct", False),
                        error_message=result_data.get("error_message"),
                        elapsed_time=result_data.get("elapsed_time", 0.0),
                        tps=result_data.get("tps", 0.0),
                        ttft=result_data.get("ttft", 0.0),
                        thinking_tokens=result_data.get("thinking_tokens", 0),
                        response_tokens=result_data.get("response_tokens", 0),
                        scoring_details=json.dumps(extra) if extra else None
                    )
                    self.db.add(result_record)
                    result_buffer.append(result_record)
                    _batch_count += 1
                    run.current_index = i + 1

                    if _batch_count >= _batch_size:
                        _flush_batch(i + 1)
                    else:
                        # Commit frequently so Live Progress reflects real-time progress
                        self.db.commit()

                except Exception as exc:
                    logger.error(f"Error evaluating sample {i}: {exc}")
                    _flush_batch(i)
                    fail_result = Result(
                        run_id=run_id,
                        task_id=sample.get("task_id", f"sample_{i}"),
                        prompt=sample.get("prompt", dataset[i].get("prompt", "")),
                        raw_response="",
                        extracted_code="",
                        correct=False,
                        error_message=str(exc),
                        elapsed_time=0.0, tps=0.0, ttft=0.0,
                        thinking_tokens=0, response_tokens=0,
                    )
                    self.db.add(fail_result)
                    run.status = "FAILED"
                    self.db.commit()
                    return

            _flush_batch(len(dataset))
            run.status = "COMPLETED"
            self.db.commit()
            logger.info(f"Benchmark run {run_id} completed successfully.")
        finally:
            self.cleanup()

    def generate_diff(self, sample: dict, result_data: dict) -> str:
        """Generate a textual diff. Override per benchmark for richer HTML views."""
        import difflib
        expected = sample.get("canonical_solution") or sample.get("answer") or sample.get("source_code", "")
        generated = result_data.get("extracted_code", result_data.get("raw_response", ""))
        if not expected:
            return "<pre>No single expected answer — this benchmark uses test-based scoring. Check the error message for details.</pre>"
        diff = difflib.unified_diff(
            str(expected).splitlines(),
            str(generated).splitlines(),
        )
        return "<pre>" + "\n".join(diff) + "</pre>"
