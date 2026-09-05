from backend.benchmarks.mcq import GenericMCQBenchmark


class MMLUProBenchmark(GenericMCQBenchmark):
    dataset_file = "mmlu_pro_full.json"
    valid_letters = "A-J"
    fetch_hint = "Run 'scripts/fetch_mmlu_pro.py' to download it."
