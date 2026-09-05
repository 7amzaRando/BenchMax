import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark
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
        path = self._resolve_dataset("ifeval_full.json", fetch_hint="Run 'scripts/fetch_ifeval.py' to download it.")
        data = self._load_json_cached(path)
        for item in data:
            if "task_id" not in item:
                item["task_id"] = item.get("key", str(item.get("_id", "unknown")))
        return data

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample.get("prompt", "")
        instruction_ids = sample.get("instruction_id_list", [])
        kwargs_list = sample.get("kwargs", [])

        gen = await self._generate(prompt, params, model_name)

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
                kw = dict(kwargs_list[index]) if index < len(kwargs_list) and isinstance(kwargs_list[index], dict) else {}
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

        return self._result(
            prompt, gen,
            extracted_code=response,
            correct=len(failed) == 0,
            error_message="; ".join(failed) if failed else None,
            scoring_details={
                "follow_instruction_list": is_following,
                "instruction_id_list": instruction_ids,
                "strict_correct": len(failed) == 0,
            },
        )
