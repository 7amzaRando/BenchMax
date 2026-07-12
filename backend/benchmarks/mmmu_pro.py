import re
import string as string_module
import base64
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file

logger = logging.getLogger(__name__)


class MMMUProBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "mmmu_pro_mini.json" if self.quick_test else "mmmu_pro_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            logger.warning("Full MMMU-Pro dataset not found, falling back to mini dataset")
            fallback = "mmmu_pro_mini.json"
            self.dataset_path = resolve_data_file(__file__, fallback)
        if not self.dataset_path:
            raise FileNotFoundError(
                "MMMU-Pro dataset not found. "
                "Run 'scripts/fetch_mmmu_pro.py' to download it."
            )
        return self._load_json_cached(self.dataset_path)

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

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
            images=images if images else None,
        )

        ac = gen.get("answer_content", "").strip()
        answer_content = (ac if ac else gen.get("raw_response", "")).strip().upper()
        pattern = r'\b([' + ''.join(letters) + r'])\b'
        extracted = re.findall(pattern, answer_content)
        answer = extracted[-1] if extracted else None
        correct = answer == sample.get("answer", "")

        return {
            "prompt": prompt,
            "raw_response": gen["raw_response"],
            "extracted_code": answer_content,
            "correct": correct,
            "error_message": None if correct else f"Expected {sample.get('answer', '')}, got {answer}",
            "elapsed_time": gen["elapsed_time"],
            "tps": gen["tps"],
            "ttft": gen["ttft"],
            "thinking_tokens": gen["thinking_tokens"],
            "response_tokens": gen["response_tokens"]
        }
