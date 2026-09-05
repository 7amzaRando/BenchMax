import logging
from backend.benchmarks.scorer_base import ScorerBenchmark

logger = logging.getLogger(__name__)


class BenchMaxCodeBenchmark(ScorerBenchmark):
    dataset_file = "code_full.json"
