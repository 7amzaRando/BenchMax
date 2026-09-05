from backend.benchmarks.mcq import GenericMCQBenchmark


class WinoGrandeBenchmark(GenericMCQBenchmark):
    dataset_file = "winogrande_full.json"
    valid_letters = "A-B"
    fetch_hint = "Run 'scripts/fetch_winogrande.py' to download it."
