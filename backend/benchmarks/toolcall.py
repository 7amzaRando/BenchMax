from backend.benchmarks.scorer_base import ScorerBenchmark


class BenchMaxToolCallBenchmark(ScorerBenchmark):
    """BenchMax ToolCall — multi-call company-environment planning (100 questions).

    Static, Docker-free, judge-free: chains, parallel select-all, argument
    traps, failure diagnosis, and state reconciliation at Meridian Industrial
    Supply Co. All scoring via shared scorers (mcq/mcq_multi/exact/exact_multi).
    """

    dataset_file = "toolcall_full.json"
