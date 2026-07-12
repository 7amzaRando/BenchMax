from backend.benchmarks.humaneval import HumanEvalBenchmark
from backend.benchmarks.mmlu_pro import MMLUProBenchmark
from backend.benchmarks.ifeval import IFEvalBenchmark
from backend.benchmarks.aime import AIMEBenchmark
from backend.benchmarks.bigcodebench import BigCodeBenchBenchmark
from backend.benchmarks.bfcl import BFCLBenchmark
from backend.benchmarks.mcp_bench import MCPBenchBenchmark
from backend.benchmarks.safety import SafetyBenchmark
from backend.benchmarks.aider_polyglot import AiderPolyglotBenchmark
from backend.benchmarks.longbench_v2 import LongBenchV2Benchmark
from backend.benchmarks.mmmu_pro import MMMUProBenchmark
from backend.benchmarks.livebench import LiveBenchBenchmark
from backend.benchmarks.personal import BenchMaxPersonalBenchmark
from backend.benchmarks.livecodebench import LiveCodeBenchBenchmark
from backend.benchmarks.speed_test import WritingSpeedTestBenchmark, CodingSpeedTestBenchmark
from backend.benchmarks.lite import BenchMaxLiteBenchmark
from backend.benchmarks.code_bench import BenchMaxCodeBenchmark
from backend.benchmarks.reason_bench import BenchMaxReasonBenchmark
from backend.benchmarks.tectonic import BenchMaxTectonicBenchmark
from backend.benchmarks.truthfulqa import TruthfulQABenchmark

__all__ = [
    "HumanEvalBenchmark",
    "MMLUProBenchmark",
    "IFEvalBenchmark",
    "AIMEBenchmark",
    "BigCodeBenchBenchmark",
    "BFCLBenchmark",
    "MCPBenchBenchmark",
    "SafetyBenchmark",
    "AiderPolyglotBenchmark",
    "LongBenchV2Benchmark",
    "MMMUProBenchmark",
    "LiveBenchBenchmark",
    "BenchMaxPersonalBenchmark",
    "LiveCodeBenchBenchmark",
    "WritingSpeedTestBenchmark",
    "CodingSpeedTestBenchmark",
    "BenchMaxLiteBenchmark",
    "BenchMaxCodeBenchmark",
    "BenchMaxReasonBenchmark",
    "BenchMaxTectonicBenchmark",
    "TruthfulQABenchmark",
]
