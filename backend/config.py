import os
from pathlib import Path
import sys

if getattr(sys, 'frozen', False):
    ROOT = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'BenchMax'
else:
    ROOT = Path(__file__).parent.parent
EXE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else None

BENCHMARKS = [
    ("HumanEval — Coding, 164 questions",                "HumanEval"),
    ("MMLU-Pro — Knowledge MCQ, 12,032 questions",       "MMLU-Pro"),
    ("IFEval — Instruction Following, 541 questions",    "IFEval"),
    ("AIME — Math, 90 questions",                        "AIME"),
    ("BigCodeBench — Coding, 1,140 questions",           "BigCodeBench"),
    ("BigCodeBench-Hard — Coding, 148 questions",        "BigCodeBench-Hard"),
    ("BFCL — Function Calling, 4,696 questions",         "BFCL"),
    ("UncensorBench — Under-Refusal Testing, 150 questions",    "UncensorBench"),
    ("LongBench-v2 — Long-Context QA, 503 questions",          "LongBench-v2"),
    ("Aider Polyglot — Code Editing, 225 questions",           "Aider Polyglot"),
    ("MMMU-Pro — Multimodal MCQ, 1,200 questions",             "MMMU-Pro"),
    ("LiveBench — Meta-Benchmark, 1,436 questions (23 sub-tasks)", "LiveBench"),
    ("LiveCodeBench — Live Code Generation, ~175 questions (test6)", "LiveCodeBench"),
    ("BenchMax Personal — Composite Score (BMS), 100 questions", "BenchMax Personal"),
    ("BenchMax Lite — All-Round, 50 questions",                  "BenchMax Lite"),
    ("BenchMax Code — Coding, 100 questions",                   "BenchMax Code"),
    ("BenchMax Reason — Reasoning, 100 questions",              "BenchMax Reason"),
    ("Writing Speed Test — Creative Writing & RP (5 prompts)", "Writing Speed Test"),
    ("Coding Speed Test — Code Generation (5 prompts)",       "Coding Speed Test"),
    ("BenchMax Tectonic — 300 questions (5 categories)",        "BenchMax Tectonic"),
    ("TruthfulQA — Truthfulness MCQ, 817 questions",           "TruthfulQA"),
    ("HellaSWAG — Commonsense Reasoning, 10,042 questions",    "HellaSWAG"),
    ("WinoGrande — Coreference Resolution, 1,267 questions",   "WinoGrande"),
    ("ARC-Challenge — Science Reasoning, 1,172 questions",      "ARC-Challenge"),
    ("CommonSenseQA — Commonsense QA, 1,221 questions",        "CommonSenseQA"),
    ("Long Context Memory — Memory Recall QA, 1,542 questions","Long Context Memory"),
    ("NIAHS — Needle-in-Haystack, 5 depths (context length from slider)", "NIAHS"),
    ("GAIA — Multi-Step Reasoning, ~165 questions (validation set)", "GAIA"),
    ("Tau3-Airline — Agentic Customer Service, 50 tasks (multi-turn)", "Tau3-Airline"),
    ("BenchMax ToolCall — Multi-Call Company Planning, 100 questions", "BenchMax ToolCall"),
]
BENCH_NAMES = [b[1] for b in BENCHMARKS]

# Rich metadata for UI: category, docker requirement, sample count, short description
BENCHMARK_META: dict[str, dict] = {
    "HumanEval":        {"category": "Coding",       "docker": True,  "samples": 164,   "short": "Code generation"},
    "MMLU-Pro":         {"category": "Knowledge",    "docker": False, "samples": 12032, "short": "General knowledge MCQ"},
    "IFEval":           {"category": "Instruction",  "docker": False, "samples": 541,   "short": "Instruction following"},
    "AIME":             {"category": "Reasoning",    "docker": False, "samples": 90,    "short": "Math reasoning"},
    "BigCodeBench":     {"category": "Coding",       "docker": True,  "samples": 1140,  "short": "Coding"},
    "BigCodeBench-Hard":{"category": "Coding",       "docker": True,  "samples": 148,   "short": "Coding — hard"},
    "BFCL":             {"category": "Tool-Use",     "docker": False, "samples": 4696,  "short": "Function calling"},
    "UncensorBench":    {"category": "Safety",       "docker": False, "samples": 150,   "short": "Safety / refusal"},
    "LongBench-v2":     {"category": "Long-Context", "docker": False, "samples": 503,   "short": "Long-context QA"},
    "Aider Polyglot":   {"category": "Coding",       "docker": True,  "samples": 225,   "short": "Multi-lang editing"},
    "MMMU-Pro":         {"category": "Vision",       "docker": False, "samples": 1200,  "short": "Multimodal MCQ"},
    "LiveBench":        {"category": "Composite",    "docker": False, "samples": 1436,  "short": "Meta-benchmark"},
    "LiveCodeBench":    {"category": "Coding",       "docker": True,  "samples": 175,   "short": "Live code gen"},
    "BenchMax Personal":{"category": "Composite",    "docker": False, "samples": 100,   "short": "Composite BMS"},
    "BenchMax Lite":    {"category": "Composite",    "docker": False, "samples": 50,    "short": "All-round MCQ"},
    "BenchMax Code":    {"category": "Coding",       "docker": False, "samples": 100,   "short": "Code reasoning (trace/bug/complexity)"},
    "BenchMax Reason":  {"category": "Reasoning",    "docker": False, "samples": 100,   "short": "Reasoning (exact-answer)"},
    "Writing Speed Test":{"category": "Speed",       "docker": False, "samples": 5,     "short": "Writing speed"},
    "Coding Speed Test":{"category": "Speed",        "docker": False, "samples": 5,     "short": "Coding speed"},
    "BenchMax Tectonic":{"category": "Composite",    "docker": False, "samples": 300,   "short": "Composite 5-cat"},
    "TruthfulQA":       {"category": "Knowledge",    "docker": False, "samples": 817,   "short": "Truthfulness"},
    "HellaSWAG":        {"category": "Reasoning",    "docker": False, "samples": 10042, "short": "Commonsense"},
    "WinoGrande":       {"category": "Reasoning",    "docker": False, "samples": 1267,  "short": "Coreference"},
    "ARC-Challenge":    {"category": "Knowledge",    "docker": False, "samples": 1172,  "short": "Science reasoning"},
    "CommonSenseQA":    {"category": "Knowledge",    "docker": False, "samples": 1221,  "short": "Commonsense QA"},
    "Long Context Memory":{"category": "Long-Context","docker": False,"samples": 1542,  "short": "Memory recall"},
    "NIAHS":            {"category": "Long-Context", "docker": False, "samples": 3,     "short": "Needle-in-haystack"},
    "GAIA":             {"category": "Tool-Use",     "docker": False, "samples": 165,   "short": "Agentic multi-turn"},
    "Tau3-Airline":   {"category": "Tool-Use",     "docker": False, "samples": 50,    "short": "Airline customer-service agent"},
    "BenchMax ToolCall": {"category": "Tool-Use",    "docker": False, "samples": 100,   "short": "Multi-call company planning"},
}
ALL_CATEGORIES = sorted({v["category"] for v in BENCHMARK_META.values()})

DATASETS = {
    "HumanEval":       ("data/humaneval_full.json",       "scripts/fetch_humaneval.py"),
    "MMLU-Pro":        ("data/mmlu_pro_full.json",        "scripts/fetch_mmlu_pro.py"),
    "IFEval":          ("data/ifeval_full.json",          "scripts/fetch_ifeval.py"),
    "AIME":            ("data/aime_full.json",            "scripts/fetch_aime.py"),
    "BigCodeBench":    ("data/bigcodebench_full.json",    "scripts/fetch_bigcodebench.py"),
    "BigCodeBench-Hard": ("data/bigcodebench_hard_full.json", "scripts/fetch_bigcodebench_hard.py"),
    "BFCL":            ("data/bfcl/bfcl_full.json",       "scripts/fetch_bfcl.py"),
    "UncensorBench":   ("data/safety/uncensor_full.json", "scripts/fetch_safety.py"),
    "Aider Polyglot":  ("data/aider_polyglot_full.json",  "scripts/fetch_aider_polyglot.py"),
    "LongBench-v2":    ("data/longbench_v2_full.json",    "scripts/fetch_longbench_v2.py"),
    "MMMU-Pro":        ("data/mmmu_pro_full.json",        "scripts/fetch_mmmu_pro.py"),
    "LiveBench":       ("data/livebench_full.json",       "scripts/fetch_livebench.py"),
    "LiveCodeBench":   ("data/livecodebench_full.json",   "scripts/fetch_livecodebench.py"),
    "BenchMax Personal": ("data/personal_full.json",       None),
    "BenchMax Lite":    ("data/lite_full.json",            None),
    "BenchMax Code":    ("data/code_full.json",            None),
    "BenchMax Reason":  ("data/reason_full.json",          None),
    "Writing Speed Test":   ("data/writing_speed_test_full.json",     None),
    "Coding Speed Test":    ("data/coding_speed_test_full.json",      None),
    "BenchMax Tectonic": ("data/tectonic_full.json",       None),
    "TruthfulQA":        ("data/truthfulqa_full.json",     "scripts/fetch_truthfulqa.py"),
    "HellaSWAG":         ("data/hellaswag_full.json",      "scripts/fetch_hellaswag.py"),
    "WinoGrande":        ("data/winogrande_full.json",     "scripts/fetch_winogrande.py"),
    "ARC-Challenge":     ("data/arc_full.json",             "scripts/fetch_arc.py"),
    "CommonSenseQA":     ("data/commonsenseqa_full.json",  "scripts/fetch_commonsenseqa.py"),
    "Long Context Memory": ("data/long_context_memory_full.json", "scripts/fetch_long_context_memory.py"),
    # NIAHS requires both the 5-sample dataset (bundled) and the Paul Graham essay corpus
    # (generated by the fetch script). The first tuple element may be a single path or a list.
    "NIAHS":               (["data/niahs_full.json", "data/niahs_corpus.json"], "scripts/fetch_niahs_corpus.py"),
    "GAIA":                ("data/gaia_full.json", "scripts/fetch_gaia.py"),
    # Tau3-Airline needs the task set plus the base DB, agent policy, and
    # user-simulator guidelines (all vendored from tau2-bench v1.0.1, MIT).
    "Tau3-Airline":        (["data/taubench_airline_full.json", "data/taubench_airline_db.json",
                            "data/taubench_airline_policy.md", "data/taubench_airline_user_guidelines.md"],
                           "scripts/fetch_taubench_airline.py"),
    "BenchMax ToolCall":   ("data/toolcall_full.json", None),
}

PROVIDER_PRESETS = {
    "LM Studio":    {"url": "http://127.0.0.1:1234/v1",        "needs_key": False},
    "Ollama":       {"url": "http://127.0.0.1:11434/v1",      "needs_key": False},
    "OpenAI":       {"url": "https://api.openai.com/v1",      "needs_key": True},
    "OpenRouter":   {"url": "https://openrouter.ai/api/v1",   "needs_key": True},
    "Groq":         {"url": "https://api.groq.com/openai/v1", "needs_key": True},
    "DeepSeek":     {"url": "https://api.deepseek.com/v1",    "needs_key": True},
    "AIMLAPI":      {"url": "https://api.aimlapi.com/v1",     "needs_key": True},
    "SiliconFlow":  {"url": "https://api.siliconflow.cn/v1",  "needs_key": True},
}

# Sandbox configuration for code execution isolation
SANDBOX_ENABLED = True           # Enable/disable sandbox restrictions
SANDBOX_MEMORY_LIMIT_MB = 256    # Memory limit per child process (MB)
SANDBOX_CPU_TIME_SEC = 300       # CPU time limit per child process (seconds)
SANDBOX_BLOCK_NETWORK = True     # Block network access in child processes
SANDBOX_BLOCK_CHILD_PROCESSES = True  # Block child process creation (cmd.exe, powershell.exe, subprocess)
SANDBOX_USE_APPCONTAINER = True  # Legacy — kept for compat, not used (Docker-only)
SANDBOX_USE_DOCKER = True        # Docker-only sandbox (clear RuntimeError if Docker unavailable)


