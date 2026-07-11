import json
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file
from backend.benchmarks.ifeval_official import instructions_registry

import nltk
for _pkg in ["punkt", "punkt_tab"]:
    try:
        nltk.data.find(f"tokenizers/{_pkg}")
    except LookupError:
        nltk.download(_pkg, quiet=True)

logger = logging.getLogger(__name__)


class IFEvalBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "ifeval_mini.json" if self.quick_test else "ifeval_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            raise FileNotFoundError(
                "IFEval dataset not found. "
                "Run 'scripts/fetch_ifeval.py' to download it."
            )
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample["prompt"]
        instruction_ids = sample.get("instruction_id_list", [])
        kwargs_list = sample.get("kwargs", [])

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        response = (gen.get("answer_content") or gen.get("raw_response", "")).strip()

        is_following = []
        for index, instr_id in enumerate(instruction_ids):
            cls = instructions_registry.INSTRUCTION_DICT.get(instr_id)
            if cls is None:
                is_following.append(False)
                continue
            try:
                instruction = cls(instr_id)
                accepted = instruction.get_instruction_args_keys()
                kw = dict(kwargs_list[index]) if index < len(kwargs_list) else {}
                kw = {k: v for k, v in kw.items() if k in accepted and v is not None}
                instruction.build_description(**kw)
                args = instruction.get_instruction_args()
                if args and "prompt" in args:
                    instruction.build_description(prompt=prompt)
                if response.strip() and instruction.check_following(response):
                    is_following.append(True)
                else:
                    is_following.append(False)
            except Exception as e:
                logger.warning("IFEval checker %s failed: %s", instr_id, e)
                is_following.append(False)

        failed = [instr_id for instr_id, ok in zip(instruction_ids, is_following) if not ok]

        return {
            "prompt": prompt,
            "raw_response": gen.get("raw_response", ""),
            "extracted_code": response,
            "correct": len(failed) == 0,
            "error_message": "; ".join(failed) if failed else None,
            "elapsed_time": gen["elapsed_time"],
            "tps": gen["tps"],
            "ttft": gen["ttft"],
            "thinking_tokens": gen["thinking_tokens"],
            "response_tokens": gen["response_tokens"],
            "scoring_details": json.dumps({
                "follow_instruction_list": is_following,
                "instruction_id_list": instruction_ids,
                "strict_correct": len(failed) == 0,
            }),
        }
