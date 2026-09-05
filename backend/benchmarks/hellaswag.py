from backend.benchmarks.mcq import GenericMCQBenchmark


class HellaSWAGBenchmark(GenericMCQBenchmark):
    dataset_file = "hellaswag_full.json"
    valid_letters = "A-D"
    fetch_hint = "Run 'scripts/fetch_hellaswag.py' to download it."
