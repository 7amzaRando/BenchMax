from backend.benchmarks.mcq import GenericMCQBenchmark


class CommonSenseQABenchmark(GenericMCQBenchmark):
    dataset_file = "commonsenseqa_full.json"
    valid_letters = "A-E"
    fetch_hint = "Run 'scripts/fetch_commonsenseqa.py' to download it."
