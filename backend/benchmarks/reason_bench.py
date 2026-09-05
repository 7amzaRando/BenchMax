import logging
from backend.benchmarks.scorer_base import ScorerBenchmark

logger = logging.getLogger(__name__)


class BenchMaxReasonBenchmark(ScorerBenchmark):
    dataset_file = "reason_full.json"
