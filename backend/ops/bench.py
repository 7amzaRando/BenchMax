"""Benchmark instantiation + client/async helpers (leaf module, no intra-ops deps)."""

import logging
import asyncio




logger = logging.getLogger(__name__)

BENCHMARK_CLASSES = {
    "HumanEval": ("backend.benchmarks.humaneval", "HumanEvalBenchmark"),
    "MMLU-Pro": ("backend.benchmarks.mmlu_pro", "MMLUProBenchmark"),
    "IFEval": ("backend.benchmarks.ifeval", "IFEvalBenchmark"),
    "AIME": ("backend.benchmarks.aime", "AIMEBenchmark"),
    "BigCodeBench": ("backend.benchmarks.bigcodebench", "BigCodeBenchBenchmark"),
    "BigCodeBench-Hard": ("backend.benchmarks.bigcodebench", "BigCodeBenchBenchmark"),
    "BFCL": ("backend.benchmarks.bfcl", "BFCLBenchmark"),
    "UncensorBench": ("backend.benchmarks.uncensor", "UncensorBenchBenchmark"),
    "LongBench-v2": ("backend.benchmarks.longbench_v2", "LongBenchV2Benchmark"),
    "Aider Polyglot": ("backend.benchmarks.aider_polyglot", "AiderPolyglotBenchmark"),
    "MMMU-Pro": ("backend.benchmarks.mmmu_pro", "MMMUProBenchmark"),
    "LiveBench": ("backend.benchmarks.livebench", "LiveBenchBenchmark"),
    "LiveCodeBench": ("backend.benchmarks.livecodebench", "LiveCodeBenchBenchmark"),
    "BenchMax Personal": ("backend.benchmarks.personal", "BenchMaxPersonalBenchmark"),
    "BenchMax Lite": ("backend.benchmarks.lite", "BenchMaxLiteBenchmark"),
    "BenchMax Code": ("backend.benchmarks.code_bench", "BenchMaxCodeBenchmark"),
    "BenchMax Reason": ("backend.benchmarks.reason_bench", "BenchMaxReasonBenchmark"),
    "Writing Speed Test": ("backend.benchmarks.speed_test", "WritingSpeedTestBenchmark"),
    "Coding Speed Test": ("backend.benchmarks.speed_test", "CodingSpeedTestBenchmark"),
    "BenchMax Tectonic": ("backend.benchmarks.tectonic", "BenchMaxTectonicBenchmark"),
    "TruthfulQA": ("backend.benchmarks.truthfulqa", "TruthfulQABenchmark"),
    "HellaSWAG": ("backend.benchmarks.hellaswag", "HellaSWAGBenchmark"),
    "WinoGrande": ("backend.benchmarks.winogrande", "WinoGrandeBenchmark"),
    "ARC-Challenge": ("backend.benchmarks.arc", "ARCBenchmark"),
    "CommonSenseQA": ("backend.benchmarks.commonsenseqa", "CommonSenseQABenchmark"),
    "Long Context Memory": ("backend.benchmarks.long_context_memory", "LongContextMemoryBenchmark"),
    "NIAHS": ("backend.benchmarks.niahs", "NIAHSBenchmark"),
    "GAIA": ("backend.benchmarks.gaia", "GAIABenchmark"),
    "Tau3-Airline": ("backend.benchmarks.taubench_airline", "Tau3AirlineBenchmark"),
    "BenchMax ToolCall": ("backend.benchmarks.toolcall", "BenchMaxToolCallBenchmark"),
}


def _build_run_params(api_url, max_tokens, sys_prompt, temp, quick_test, disable_rep_detection, context_length=None):
    """Build the standard params dict stored in Run.parameters."""
    params = {"api_url": api_url, "max_completion_tokens": max_tokens, "system_prompt": sys_prompt}
    if temp is not None:
        params["temperature"] = temp
    params["quick_test"] = quick_test
    params["disable_repetition_detection"] = disable_rep_detection
    if context_length is not None:
        params["context_length"] = context_length
    return params


def _make_client(api_url: str, api_key: str):
    from backend.lm_studio.client import LMStudioClient
    return LMStudioClient(base_url=api_url, api_key=api_key or None)


def _run_async(coro):
    """Run an async coroutine from sync code with a fresh event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except RuntimeError:
            pass


def _instantiate_benchmark(benchmark_name: str, db, client, quick_test=False, hard=False):
    import inspect as _inspect
    entry = BENCHMARK_CLASSES.get(benchmark_name)
    if not entry:
        raise ValueError(f"Unknown benchmark: {benchmark_name}")
    mod_path, cls_name = entry
    mod = __import__(mod_path, fromlist=[cls_name])
    cls = getattr(mod, cls_name)
    # hard=True comes from either the explicit flag or the "-Hard" preset name.
    # Only pass it when the benchmark class actually accepts it.
    wants_hard = bool(hard) or "hard" in benchmark_name.lower()
    kwargs = {}
    if wants_hard:
        try:
            params = _inspect.signature(cls.__init__).parameters
            if "hard" in params:
                kwargs["hard"] = True
        except (TypeError, ValueError):
            pass
    return cls(db, client, quick_test=quick_test, **kwargs)
