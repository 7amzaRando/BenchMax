import string as string_module
import base64
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark
from backend.benchmarks.scoring import score_mcq

logger = logging.getLogger(__name__)


class MMMUProBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        path = self._resolve_dataset("mmmu_pro_full.json", fetch_hint="Run 'scripts/fetch_mmmu_pro.py' to download it.")
        return self._load_json_cached(path)

    def _find_data_dir(self) -> Path:
        """Find data directory, handling PyInstaller frozen builds."""
        base = Path(__file__).parents[2] / "data"
        if base.exists():
            return base
        if getattr(sys, 'frozen', False):
            for candidate in [
                Path(sys.executable).parent / "data",
                Path(sys.executable).parent.parent / "data",
                Path.cwd() / "data",
            ]:
                if candidate.exists():
                    return candidate
        return base

    def _load_images(self, sample: Dict[str, Any]) -> List[str]:
        """Load images for a sample from disk, return as base64 strings."""
        data_dir = self._find_data_dir()
        b64s = []
        for rel_path in sample.get("image_paths", []):
            img_path = data_dir / rel_path
            if img_path.exists():
                b64s.append(base64.b64encode(img_path.read_bytes()).decode("utf-8"))
            else:
                logger.warning(f"Image not found: {img_path}")
        return b64s

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        options = sample.get("options", [])
        num_options = len(options)
        letters = list(string_module.ascii_uppercase[:num_options])
        prompt = f"{sample.get('question', '')}\n\nOptions:\n"
        for letter, opt in zip(letters, options):
            prompt += f"  {letter}. {opt}\n"
        prompt += "\nAnswer with only the letter of the correct option."

        images = self._load_images(sample)

        gen = await self._generate(prompt, params, model_name, images=images if images else None)

        ac = gen.get("answer_content", "").strip()
        answer_content = (ac if ac else gen.get("raw_response", "")).strip()
        if not letters:
            return self._result(
                prompt, gen,
                extracted_code=answer_content,
                correct=False,
                error_message="No options in sample",
                scoring_details={"category": sample.get("subject", "unknown")},
            )
        universe = f"A-{letters[-1]}"
        correct, err = score_mcq(answer_content, sample.get("answer", ""),
                                 universe, single_answer=True)

        cat = sample.get("subject", "unknown")
        details = {"category": cat}
        if not images and sample.get("image_paths"):
            # Text-only run (images missing/unreadable) — flag it so a fail
            # reads as a data problem, not a model failure.
            details["images_missing"] = True
            logger.warning("MMMU-Pro %s: images missing, running text-only",
                           sample.get("task_id", "unknown"))
        return self._result(
            prompt, gen,
            extracted_code=answer_content,
            correct=correct,
            error_message=None if correct else err,
            scoring_details=details,
        )
