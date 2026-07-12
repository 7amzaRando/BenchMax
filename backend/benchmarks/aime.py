import re
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file

logger = logging.getLogger(__name__)

def extract_aime_answer(text: str) -> int:
    """Extract final integer answer from AIME model response.

    Strategy:
    1. Look for 'Answer:' or 'answer:' followed by a number
    2. Look for 'boxed{N}' or '\\boxed{N}' pattern
    3. Fall back to the last integer (0-999) in the response
    """
    # Pattern 1: "Answer: N" or "answer: N" or "Answer: N."
    matches = re.findall(r'[Aa]nswer\s*:\s*(\d+)', text)
    if matches:
        val = int(matches[-1])
        if 0 <= val <= 999:
            return val

    # Pattern 2: \boxed{N} or boxed{N}
    matches = re.findall(r'\\{0,2}boxed\{(\d+)\}', text)
    if matches:
        val = int(matches[-1])
        if 0 <= val <= 999:
            return val

    # Pattern 3: "The answer is N" or "N is the answer"
    matches = re.findall(r'(?:answer|result|value)\s+is\s+(\d+)', text, re.IGNORECASE)
    if matches:
        val = int(matches[-1])
        if 0 <= val <= 999:
            return val

    # Pattern 4: Last integer 0-999 in the response
    all_nums = re.findall(r'(?<!\d)(\d+)(?!\d)', text)
    if all_nums:
        # Take the last number that is 0-999
        for candidate in reversed(all_nums):
            val = int(candidate)
            if 0 <= val <= 999:
                return val

    return -1


class AIMEBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "aime_mini.json" if self.quick_test else "aime_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            self.dataset_path = resolve_data_file(__file__, "aime_mini.json")
            logger.warning("Full AIME dataset not found, falling back to mini dataset")
        if not self.dataset_path:
            raise FileNotFoundError("AIME dataset not found (tried full and mini)")
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = f"{sample['problem']}\n\n"
        prompt += "Think step by step, then provide your final answer as 'Answer: N' where N is the integer between 0 and 999."

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        answer_content = (gen.get("answer_content") or gen.get("raw_response", "")).strip()
        extracted = extract_aime_answer(answer_content)
        expected = int(sample.get("answer", "0"))
        correct = extracted == expected

        error_msg = None
        if not correct:
            if extracted == -1:
                error_msg = f"No valid integer answer found in response"
            else:
                error_msg = f"Expected {expected}, extracted {extracted}"

        return {
            "prompt": prompt,
            "raw_response": gen["raw_response"],
            "extracted_code": answer_content,
            "correct": correct,
            "error_message": error_msg,
            "elapsed_time": gen["elapsed_time"],
            "tps": gen["tps"],
            "ttft": gen["ttft"],
            "thinking_tokens": gen["thinking_tokens"],
            "response_tokens": gen["response_tokens"]
        }
