import json
import logging
import random
import threading
from pathlib import Path
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


def _random_needle() -> str:
    """Generate a fresh 8-digit secret key for each sample so the benchmark
    cannot be gamed by memorizing a fixed value."""
    return str(random.randint(10000000, 99999999))


class NIAHSBenchmark(BaseBenchmark):
    _corpus: str | None = None
    _corpus_lock = threading.Lock()

    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def _load_corpus(self) -> str:
        if NIAHSBenchmark._corpus is None:
            with NIAHSBenchmark._corpus_lock:
                if NIAHSBenchmark._corpus is None:
                    corpus_path = Path(__file__).parents[2] / "data" / "niahs_corpus.json"
                    if not corpus_path.exists():
                        raise FileNotFoundError(
                            f"Corpus not found at {corpus_path}. "
                            "Run 'python scripts/fetch_niahs_corpus.py' to download Paul Graham essays."
                        )
                    with open(corpus_path, encoding="utf-8") as f:
                        NIAHSBenchmark._corpus = json.load(f)["corpus"]
                    logger.info(f"Loaded NIAHS corpus: {len(NIAHSBenchmark._corpus):,} chars")
        return NIAHSBenchmark._corpus

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset(
            "niahs_full.json",
            fetch_hint="Run 'python scripts/fetch_niahs_corpus.py' to generate the NIAHS corpus."
        )
        raw = self._load_json_cached(path)
        # Collect all depths from the dataset (5 entries: 10/25/50/75/90%).
        # Multi-needle design: 3 samples, each with ALL 5 needles inserted — 5× speedup
        # vs 15 separate single-needle haystacks (TTFT dominates).
        depths = [float(s.get("depth", 0.5)) for s in raw] if raw else [0.10, 0.25, 0.50, 0.75, 0.90]
        # Preserve original behaviour for quick_test? No — 3 samples is already fast;
        # quick_test still returns 3 (not 15), giving the same 5× win.
        num_runs = 3
        return [
            {"task_id": f"niahs_run{run_idx}", "depths": list(depths)}
            for run_idx in range(num_runs)
        ]

    def _generate_haystack(self, target_tokens: int) -> str:
        corpus = self._load_corpus()
        target_chars = target_tokens * CHARS_PER_TOKEN
        if len(corpus) >= target_chars:
            return corpus[:target_chars]
        repeats = (target_chars // len(corpus)) + 1
        return (corpus * repeats)[:target_chars]

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        ctx_len = params.get("context_length", 65536)
        depths: List[float] = sample.get("depths") or [0.10, 0.25, 0.50, 0.75, 0.90]

        # Generate 5 distinct 8-digit needles (depth → value)
        needles: Dict[str, str] = {}
        used = set()
        for d in depths:
            for _ in range(10):
                v = _random_needle()
                if v not in used:
                    needles[str(d)] = v
                    used.add(v)
                    break
            else:
                needles[str(d)] = _random_needle()

        haystack = self._generate_haystack(ctx_len)
        original = haystack
        doc = haystack
        # Insert deepest first so shallower insert_pos (based on original) stays valid
        for d in sorted(depths, reverse=True):
            key = str(d)
            paragraph = f"\n\nHidden Key at {int(d * 100)}% = {needles[key]}\n\n"
            pos = int(len(original) * d)
            doc = doc[:pos] + paragraph + doc[pos:]

        depth_labels = ", ".join(f"{int(d * 100)}%" for d in depths)
        prompt = (
            f"Find all hidden keys in the following document.\n\n"
            f"Document:\n{doc}\n\n"
            f"There are {len(depths)} hidden keys at depths {depth_labels}.\n"
            f"List all values — one per line or comma-separated. "
            f"Respond with ONLY the values, nothing else."
        )

        gen = await self._generate(prompt, params, model_name)
        response = (gen.get("answer_content") or gen.get("raw_response", "")).strip()

        per_depth_correct: Dict[str, bool] = {}
        for d in depths:
            key = str(d)
            per_depth_correct[key] = needles[key] in response

        # Overall strict: all 5 must be found
        correct = all(per_depth_correct.values())

        if correct:
            error_message = None
        elif not response and gen.get("stream_timed_out"):
            error_message = "Model produced no output (stream timed out during generation)."
        elif not response:
            raw = (gen.get("raw_response") or "").strip()
            expected_str = ", ".join(f"{int(float(k) * 100)}%:{v}" for k, v in needles.items())
            error_message = (
                f"Expected keys {{{expected_str}}}, got empty response. "
                f"Raw model output: '{raw[:200]}'"
            ) if raw else f"Expected keys {{{expected_str}}}, but the model returned no output."
        else:
            missing = [f"{int(float(k) * 100)}%={v}" for k, v in needles.items() if not per_depth_correct[k]]
            found = [f"{int(float(k) * 100)}%={v}" for k, v in needles.items() if per_depth_correct[k]]
            if missing and found:
                error_message = f"Missing {', '.join(missing)}; found {', '.join(found)}; response: '{response[:200]}'"
            elif missing:
                error_message = f"Missing all keys {', '.join(missing)}; response: '{response[:200]}'"
            else:
                error_message = f"Unexpected scoring state; response: '{response[:200]}'"

        return self._result(
            prompt, gen,
            extracted_code=response,
            correct=correct,
            error_message=error_message,
            scoring_details={
                "expected": needles,  # depth_str -> needle value (new multi-needle schema)
                "per_depth_correct": per_depth_correct,
                "depths": depths,
                "depth": depths[0] if depths else 0.5,  # legacy single-depth key for backward compat
                "context_length": ctx_len,
                "accuracy": sum(per_depth_correct.values()) / len(per_depth_correct) if per_depth_correct else 0.0,
            },
        )
