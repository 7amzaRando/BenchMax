import html
import json
import difflib
import logging
import sys
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.database import Run, Result
from backend.lm_studio.client import LMStudioClient

logger = logging.getLogger(__name__)

# In-memory per-sample progress (run_id -> completed samples). The DB-backed
# run.current_index only commits on batch flush (every 5, or 25 for huge
# suites), so poll() reads this for live per-sample freshness with zero
# extra DB writes. Cleared when the run ends (see run_evaluation finally).
_live_progress: Dict[int, int] = {}
_live_progress_lock = threading.Lock()


def set_live_progress(run_id: int, completed: int) -> None:
    with _live_progress_lock:
        _live_progress[run_id] = completed


def get_live_progress(run_id: int) -> int | None:
    with _live_progress_lock:
        return _live_progress.get(run_id)


def clear_live_progress(run_id: int) -> None:
    with _live_progress_lock:
        _live_progress.pop(run_id, None)

# Batch commit size — flush results to DB every N samples to balance
# live-progress visibility against SQLite write amplification.
# Base value 5 keeps NIAHS (3 samples) and other small suites live; large
# suites (>500 samples like HellaSWAG/MMLU-Pro) use adaptive 25 to cut WAL pressure.
_BATCH_SIZE = 5
_BATCH_SIZE_LARGE = 25
_BATCH_SIZE_LARGE_THRESHOLD = 500
# Abort a run after this many consecutive sample failures (points at a
# systemic problem rather than isolated bad samples).
_MAX_CONSECUTIVE_FAILURES = 10


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
    _dataset_cache_max = 10  # Max cached datasets before LRU eviction
    _dataset_cache_lock = __import__("threading").Lock()

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
        """Load a JSON file with class-level caching (LRU eviction at 10 entries)."""
        key = f"{self.__class__.__name__}:{path}"
        with self._dataset_cache_lock:
            if key in self._dataset_cache:
                return self._dataset_cache[key]
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._dataset_cache[key] = data
            # LRU eviction: remove oldest entries when cache exceeds max
            if len(self._dataset_cache) > self._dataset_cache_max:
                oldest_keys = list(self._dataset_cache.keys())[:len(self._dataset_cache) - self._dataset_cache_max]
                for k in oldest_keys:
                    self._dataset_cache.pop(k, None)
            return data

    def _result(
        self,
        prompt: str,
        gen: dict,
        *,
        extracted_code: str = "",
        correct: bool = False,
        error_message: str | None = None,
        scoring_details: dict | None = None,
        **extra,
    ) -> dict:
        """Build the standard result dict from a generate_completion() output."""
        d = {
            "prompt": prompt,
            "raw_response": gen.get("raw_response", ""),
            "extracted_code": extracted_code,
            "correct": correct,
            "error_message": error_message,
            "elapsed_time": gen.get("elapsed_time", 0.0),
            "tps": gen.get("tps", 0.0),
            "ttft": gen.get("ttft", 0.0),
            "thinking_tokens": gen.get("thinking_tokens", 0),
            "response_tokens": gen.get("response_tokens", 0),
            "prompt_tokens": gen.get("prompt_tokens", 0),
        }
        if scoring_details is not None:
            d["scoring_details"] = scoring_details
        d.update(extra)
        return d

    def _resolve_dataset(
        self,
        full_name: str,
        mini_name: str | None = None,
        fetch_hint: str = "",
    ) -> str:
        """Resolve dataset path with full→mini fallback. Returns the resolved path.
        Raises FileNotFoundError with a helpful message if neither exists."""
        if mini_name is None:
            mini_name = full_name.replace("_full.", "_mini.")
        resolved = resolve_data_file(__file__, full_name if not self.quick_test else mini_name)
        if not resolved:
            resolved = resolve_data_file(__file__, mini_name)
            if resolved:
                logger.warning(f"Full dataset {full_name} not found, falling back to mini")
        if not resolved:
            msg = f"Dataset {full_name} not found."
            if fetch_hint:
                msg += f" {fetch_hint}"
            raise FileNotFoundError(msg)
        return resolved

    async def _generate(
        self,
        prompt: str,
        params: dict,
        model_name: str,
        *,
        stop_tokens: list | None = None,
        images: list | None = None,
    ) -> dict:
        """Call generate_completion with standard param extraction from the run params dict."""
        kwargs = dict(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=stop_tokens if stop_tokens is not None else params.get("stop_tokens"),
            model_name=model_name,
        )
        if images:
            kwargs["images"] = images
        return await self.client.generate_completion(**kwargs)

    async def _generate_chat(
        self,
        messages: List[Dict[str, str]],
        params: dict,
        model_name: str,
        *,
        stop_tokens: list | None = None,
        images: list | None = None,
    ) -> dict:
        """Call generate_chat_completion with a pre-built messages array.

        This enables true multi-turn conversations by passing the full message
        history directly to the OpenAI-compatible messages API, rather than
        flattening into a single prompt string.

        Args:
            messages: Full message history [{"role": "user", "content": "..."}, ...].
            params: Run parameters dict (temperature, max_completion_tokens, etc.).
            model_name: Model ID to use.
            stop_tokens: Optional stop sequences (overrides params).
            images: Optional list of base64 PNG images (appended to last user message).

        Returns:
            Same dict as generate_completion().
        """
        kwargs = dict(
            messages=messages,
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=stop_tokens if stop_tokens is not None else params.get("stop_tokens"),
            model_name=model_name,
        )
        if images:
            kwargs["images"] = images
        return await self.client.generate_chat_completion(**kwargs)

    def cleanup(self) -> None:
        """Override to release resources after benchmark finishes."""
        pass

    async def run_evaluation(self, run_id: int, params: Dict[str, Any]) -> None:
        """
        Main runner loop. Executes the benchmark sequentially, handles
        database state tracking, and listens for pause/halt commands.
        """
        halt_ev = params.get("_halt_event")
        run_logger = logging.LoggerAdapter(logger, {"run_id": run_id})

        def _is_halted() -> bool:
            if halt_ev and halt_ev.is_set():
                return True
            return False

        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            run_logger.error("Run ID not found in database.")
            return

        run.status = "RUNNING"
        self.db.commit()

        dataset = self.load_dataset()
        run.total_samples = len(dataset)
        self.db.commit()

        if not dataset:
            run_logger.error(f"Benchmark {run.benchmark_name} loaded empty dataset — marking FAILED.")
            run.status = "FAILED"
            self.db.commit()
            return

        start_index = run.current_index
        model_name = run.model_name
        # Expose run_id to evaluate_sample for live turn tracking (multi-turn)
        params["_run_id"] = run_id

        run_logger.info(
            "Starting %s | model=%s | samples=%d | index=%d/%d | temp=%.2f | max_tokens=%s | quick_test=%s",
            run.benchmark_name, model_name, len(dataset), start_index, len(dataset),
            params.get("temperature", 0.0), params.get("max_completion_tokens"),
            self.quick_test,
        )

        # When resuming from a midpoint, purge any partial/duplicate results at
        # or after the resume point (e.g. a FAILED sample at current_index that
        # would otherwise be re-scored twice). Skip for fresh runs (index 0).
        if start_index > 0:
            resume_task_ids = {s.get("task_id") for s in dataset[start_index:] if s.get("task_id")}
            if resume_task_ids:
                stale_results = self.db.query(Result).filter(
                    Result.run_id == run_id,
                    Result.task_id.in_(resume_task_ids),
                ).all()
                if stale_results:
                    logger.info(
                        f"Run {run_id} resuming from index {start_index} — "
                        f"purging {len(stale_results)} stale result(s) at/after resume point."
                    )
                    for sr in stale_results:
                        self.db.delete(sr)
                    self.db.commit()

        logger.info(f"Starting benchmark {run.benchmark_name} for model {model_name} from index {start_index}/{len(dataset)}")

        _batch_count = 0
        result_buffer = []
        consecutive_failures = 0

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
                    run_logger.info("Halted via in-memory signal at index %d.", i)
                    _flush_batch(i)
                    run.status = "HALTED"
                    self.db.commit()
                    return

                # Check for pause / abort periodically (not every iteration) to avoid
                # excessive DB round-trips for large datasets. Halt is checked via the
                # in-memory event above; the DB refresh is only needed for PAUSED status.
                if i % 50 == 0 or i == len(dataset) - 1:
                    try:
                        self.db.refresh(run)
                    except Exception:
                        # Run row deleted mid-run (e.g. cleared history) — abort quietly.
                        run_logger.warning("Deleted during execution — aborting loop.")
                        return
                    if run.status == "PAUSED":
                        run_logger.info("Paused at index %d.", i)
                        run.current_index = i
                        self.db.commit()
                        return
                    elif run.status in ("HALTED", "FAILED"):
                        run_logger.info("Halted/aborted at index %d.", i)
                        return

                sample = dataset[i]

                try:
                    result_data = await self.evaluate_sample(sample, params, model_name)

                    task_id = sample.get("task_id", f"sample_{i}")
                    run_logger.debug(
                        "[%d/%d] %s correct=%s tps=%.1f ttft=%.3f tokens=%d%s",
                        i + 1, len(dataset), task_id,
                        result_data.get("correct", False),
                        result_data.get("tps", 0.0),
                        result_data.get("ttft", 0.0),
                        result_data.get("response_tokens", 0),
                        f" error={result_data.get('error_message', '')[:80]}" if result_data.get("error_message") else "",
                    )

                    if _is_halted():
                        run_logger.info("Halted mid-sample at index %d — discarding result.", i)
                        _flush_batch(i)
                        run.status = "HALTED"
                        self.db.commit()
                        return

                    rep_detected = not getattr(self.client, '_rep_disabled', False) and getattr(self.client, '_repetition_detected', False)
                    if rep_detected:
                        run_logger.warning("Repetition detected at index %d, skipping sample.", i)
                        rep_result = Result(
                            run_id=run_id,
                            task_id=sample.get("task_id", f"sample_{i}"),
                            prompt=result_data.get("prompt"),
                            raw_response=result_data.get("raw_response", ""),
                            extracted_code="",
                            correct=False,
                            error_message="Repetition detected — model output is looping (sample skipped)",
                            elapsed_time=result_data.get("elapsed_time", 0.0),
                            tps=result_data.get("tps", 0.0),
                            ttft=result_data.get("ttft", 0.0),
                            thinking_tokens=result_data.get("thinking_tokens", 0),
                            response_tokens=result_data.get("response_tokens", 0),
                        )
                        self.db.add(rep_result)
                        run.current_index = i + 1
                        self.db.commit()
                        set_live_progress(run_id, i + 1)
                        continue

                    if result_data.get("stream_timed_out"):
                        if not result_data.get("error_message"):
                            result_data["error_message"] = "Stream timed out — no tokens received for 60s (sample skipped)"
                        result_data["correct"] = False

                    standard_keys = {"prompt", "raw_response", "extracted_code",
                                     "correct", "error_message", "elapsed_time",
                                     "tps", "ttft", "thinking_tokens", "response_tokens",
                                     "thinking_content", "answer_content",
                                     "prompt_tokens", "stream_timed_out"}
                    extra = {k: v for k, v in result_data.items() if k not in standard_keys}
                    if "scoring_details" in result_data:
                        sd = result_data["scoring_details"]
                        scoring_details = json.dumps(sd) if not isinstance(sd, str) else sd
                    elif extra:
                        scoring_details = json.dumps(extra)
                    else:
                        scoring_details = None
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
                        prompt_tokens=result_data.get("prompt_tokens", 0),
                        scoring_details=scoring_details
                    )
                    result_buffer.append(result_record)
                    _batch_count += 1
                    consecutive_failures = 0
                    run.current_index = i + 1
                    set_live_progress(run_id, i + 1)

                    # Adaptive flush: NIAHS (3 samples) and other tiny suites need
                    # per-sample visibility (otherwise RUNNING stays 0/3 until the end).
                    if len(dataset) <= 10:
                        effective_bs = 1
                    else:
                        effective_bs = _BATCH_SIZE_LARGE if len(dataset) > _BATCH_SIZE_LARGE_THRESHOLD else _BATCH_SIZE
                    if _batch_count >= effective_bs:
                        _flush_batch(i + 1)

                except (SystemExit, KeyboardInterrupt):
                    raise
                except Exception as exc:
                    # A single bad sample (transient HTTP error, parse failure,
                    # LM Studio hiccup) should NOT kill the whole run. Record a
                    # failed result and keep going; only abort the run if many
                    # samples fail in a row (pointing at a systemic problem).
                    run_logger.error("Error evaluating sample %d: %s", i, exc)
                    _flush_batch(i)
                    fail_result = Result(
                        run_id=run_id,
                        task_id=sample.get("task_id", f"sample_{i}"),
                        prompt=sample.get("prompt", ""),
                        raw_response="",
                        extracted_code="",
                        correct=False,
                        error_message=str(exc),
                        elapsed_time=0.0, tps=0.0, ttft=0.0,
                        thinking_tokens=0, response_tokens=0,
                    )
                    self.db.add(fail_result)
                    run.current_index = i + 1
                    self.db.commit()
                    set_live_progress(run_id, i + 1)
                    consecutive_failures += 1
                    if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                        run_logger.error("Aborted — %d consecutive sample failures.", consecutive_failures)
                        _flush_batch(i + 1)
                        run.status = "FAILED"
                        self.db.commit()
                        return
                    continue

            _flush_batch(len(dataset))
            run.status = "COMPLETED"
            self.db.commit()
            run_logger.info("Completed successfully — %d samples.", len(dataset))
        finally:
            clear_live_progress(run_id)
            self.cleanup()

    @staticmethod
    def _question_text(sample: dict, result_data: dict) -> str:
        """Best-effort question text for diff fallback.

        Prefers the stored prompt (the exact text sent to the model, which
        covers dynamic prompts like NIAHS haystacks), then falls back to
        known sample keys across all benchmark schemas.
        """
        stored = (result_data.get("prompt") or "").strip()
        if stored:
            return stored
        for key in ("prompt", "question", "problem", "question_content",
                    "instruction", "context"):
            val = sample.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # Tau3-Airline: user_scenario dict
        scenario = sample.get("user_scenario")
        if isinstance(scenario, dict) and scenario:
            try:
                return json.dumps(scenario, ensure_ascii=False, indent=2)
            except Exception:
                return str(scenario)
        # Multi-turn (GAIA/Tau3): first user turn
        turns = sample.get("turns")
        if isinstance(turns, list) and turns:
            for t in turns:
                if isinstance(t, dict) and t.get("content"):
                    return str(t["content"])
        # BFCL-style function prompt
        funcs = sample.get("function")
        if funcs:
            try:
                return json.dumps(funcs, ensure_ascii=False, indent=2)
            except Exception:
                return str(funcs)
        return ""

    @staticmethod
    def _model_text(result_data: dict) -> str:
        """Best-effort model answer for diff fallback."""
        extracted = (result_data.get("extracted_code") or "").strip()
        if extracted:
            return extracted
        return (result_data.get("raw_response") or "").strip()

    @staticmethod
    def _extra_rules_html(sample: dict) -> str:
        """Optional scoring-rule hints (IFEval instructions, uncensor keywords)."""
        extras = []
        ids = sample.get("instruction_id_list")
        if isinstance(ids, list) and ids:
            extras.append("Rules: " + html.escape(", ".join(str(i) for i in ids)))
        kws = sample.get("expected_refusal_keywords")
        if isinstance(kws, list) and kws:
            extras.append("Expected keywords: " + html.escape(", ".join(str(k) for k in kws)))
        if not extras:
            return ""
        items = "".join(f'<div style="color:#94a3b8;font-size:12px">{e}</div>' for e in extras)
        return f'<div style="margin-bottom:12px">{items}</div>'

    def _generate_question_answer_diff(self, sample: dict, result_data: dict) -> str:
        """Fallback when there is no single expected answer (test/rule-based scoring).

        Always shows the question + model answer instead of a bare notice, so
        every benchmark diff is useful (IFEval, NIAHS, speed tests, uncensor,
        Aider Polyglot, Tau3-Airline, ...).
        """
        question = self._question_text(sample, result_data)
        model = self._model_text(result_data)
        extras_html = self._extra_rules_html(sample)
        # Truncate very long prompts (NIAHS 64K haystacks, long-context) for display.
        q_display = (question[:3000] + "…") if len(question) > 3000 else question
        m_display = (model[:4000] + "…") if len(model) > 4000 else model
        return (
            '<div style="font-family:system-ui,sans-serif;padding:16px;border-radius:8px;'
            'background:#1e293b;border:1px solid #334155">'
            '<div style="color:#94a3b8;font-size:13px;margin-bottom:12px">'
            'No single expected answer — this benchmark uses test-based or rule-based scoring.</div>'
            f'{extras_html}'
            '<div style="color:#64748b;font-size:11px;text-transform:uppercase;'
            'letter-spacing:0.05em;margin-bottom:6px">Question</div>'
            f'<pre style="padding:10px;background:#0f172a;color:#e2e8f0;border-radius:6px;'
            'font-size:12px;white-space:pre-wrap;word-break:break-word;'
            f'max-height:300px;overflow:auto;margin-bottom:12px">{html.escape(q_display or "(no question stored)")}</pre>'
            '<div style="color:#64748b;font-size:11px;text-transform:uppercase;'
            'letter-spacing:0.05em;margin-bottom:6px">Model Answer</div>'
            f'<pre style="padding:10px;background:#0f172a;color:#e2e8f0;border-radius:6px;'
            'font-size:12px;white-space:pre-wrap;word-break:break-word;'
            f'max-height:300px;overflow:auto">{html.escape(m_display or "(no model output)")}</pre>'
            '</div>'
        )

    def generate_diff(self, sample: dict, result_data: dict) -> str:
        """Generate a visual comparison. Override per benchmark for richer views."""
        expected = (
            sample.get("canonical_solution")
            or sample.get("answer")
            or sample.get("answers")
            or sample.get("ground_truth")
            or sample.get("best_answer")
            or ""
        )
        # Lists (BFCL answer arrays, exact_multi) render better as JSON than repr.
        if isinstance(expected, (list, dict)):
            try:
                expected = json.dumps(expected, ensure_ascii=False, indent=2)
            except Exception:
                expected = str(expected)
        extracted = result_data.get("extracted_code", "")
        raw = result_data.get("raw_response", "")

        if not expected or not str(expected).strip():
            return self._generate_question_answer_diff(sample, result_data)

        expected_str = str(expected).strip()
        extracted_str = str(extracted).strip()
        raw_str = str(raw).strip()

        # Match check: extracted answer matches expected
        if extracted_str and extracted_str == expected_str:
            return (
                '<div style="font-family:system-ui,sans-serif;padding:20px;border-radius:8px;'
                'background:#1e293b;border:1px solid #065f46;text-align:center">'
                '<div style="color:#a7f3d0;font-size:14px;font-weight:600;margin-bottom:8px">&#10003; Answer matches expected</div>'
                f'<div style="display:inline-block;background:#065f46;color:#a7f3d0;padding:6px 16px;'
                f'border-radius:6px;font-family:monospace;font-size:15px">{html.escape(expected_str)}</div>'
                '</div>'
            )

        # Short answers (MCQ, exact numeric) — side-by-side comparison
        if len(expected_str) < 200:
            display_answer = extracted_str if extracted_str else raw_str[:300]
            return (
                '<div style="font-family:system-ui,sans-serif;padding:16px;border-radius:8px;'
                'background:#1e293b;border:1px solid #ef4444">'
                '<div style="display:flex;gap:12px;margin-bottom:12px">'
                '<div style="flex:1">'
                '<div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Expected</div>'
                f'<div style="background:#065f46;color:#a7f3d0;padding:10px 14px;border-radius:6px;'
                f'font-family:monospace;font-size:15px;font-weight:600;text-align:center">'
                f'{html.escape(expected_str)}</div></div>'
                '<div style="display:flex;align-items:end;padding-bottom:10px;color:#64748b;font-size:18px">&ne;</div>'
                '<div style="flex:1">'
                '<div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Model Answer</div>'
                f'<div style="background:#7f1d1d;color:#fecaca;padding:10px 14px;border-radius:6px;'
                f'font-family:monospace;font-size:15px;font-weight:600;text-align:center">'
                f'{html.escape(display_answer[:200])}</div></div>'
                '</div>'
                f'<details style="margin-top:8px"><summary style="color:#64748b;font-size:11px;cursor:pointer;'
                f'text-transform:uppercase;letter-spacing:0.05em">Full model response</summary>'
                f'<pre style="margin-top:8px;padding:10px;background:#0f172a;color:#94a3b8;border-radius:6px;'
                f'font-size:11px;white-space:pre-wrap;word-break:break-word;max-height:200px;overflow:auto">'
                f'{html.escape(raw_str[:2000])}</pre></details>'
                '</div>'
            )

        # Longer content (code) — colored unified diff
        diff = list(difflib.unified_diff(
            expected_str.splitlines(), extracted_str.splitlines(),
            fromfile="expected", tofile="model output", n=1,
        ))
        if not diff:
            return (
                '<div style="font-family:system-ui,sans-serif;padding:20px;border-radius:8px;'
                'background:#1e293b;border:1px solid #065f46;text-align:center">'
                '<div style="color:#a7f3d0;font-size:14px;font-weight:600">&#10003; Output matches expected</div></div>'
            )
        lines_html = []
        for line in diff:
            escaped = html.escape(line.rstrip())
            if line.startswith("+") and not line.startswith("+++"):
                lines_html.append(f'<div style="background:#065f4640;color:#a7f3d0;padding:1px 8px">{escaped}</div>')
            elif line.startswith("-") and not line.startswith("---"):
                lines_html.append(f'<div style="background:#7f1d1d40;color:#fecaca;padding:1px 8px">{escaped}</div>')
            elif line.startswith("@@"):
                lines_html.append(f'<div style="color:#60a5fa;padding:1px 8px;font-weight:600">{escaped}</div>')
            else:
                lines_html.append(f'<div style="color:#e2e8f0;padding:1px 8px">{escaped}</div>')
        return (
            '<div style="font-family:monospace;font-size:12px;background:#0f172a;'
            'border-radius:8px;border:1px solid #334155;overflow-x:auto">'
            '<div style="padding:8px 12px;border-bottom:1px solid #334155;color:#64748b;font-size:11px;'
            'text-transform:uppercase;letter-spacing:0.05em">Code Diff</div>'
            f'<div style="padding:4px 0">{"".join(lines_html)}</div></div>'
        )
