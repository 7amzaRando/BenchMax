from backend.benchmarks.mcq import GenericMCQBenchmark
from backend.benchmarks.scoring import score_mcq


class TruthfulQABenchmark(GenericMCQBenchmark):
    dataset_file = "truthfulqa_full.json"
    valid_letters = "A-B"
    fetch_hint = "Run 'scripts/fetch_truthfulqa.py' to download it."

    async def evaluate_sample(self, sample, params, model_name):
        """TruthfulQA uses choice_A/choice_B fields instead of options list."""
        prompt = (
            f"Question: {sample.get('question', '')}\n\n"
            f"Options:\n"
            f"  A. {sample.get('choice_A', '')}\n"
            f"  B. {sample.get('choice_B', '')}\n\n"
            f"Answer with only the letter of the correct option."
        )
        gen = await self._generate(prompt, params, model_name)
        answer_content = (gen.get("answer_content") or gen.get("raw_response", "")).strip()
        correct, err = score_mcq(answer_content, sample.get("answer", ""),
                                 "AB", single_answer=True)
        return self._result(
            prompt, gen,
            extracted_code=answer_content,
            correct=correct,
            error_message=None if correct else err,
        )
