from backend.benchmarks.mcq import GenericMCQBenchmark


class ARCBenchmark(GenericMCQBenchmark):
    dataset_file = "arc_full.json"
    valid_letters = "A-D"
    fetch_hint = "Run 'scripts/fetch_arc.py' to download it."
