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
    ("MCP-Bench — MCP Tool Calling, 5 questions (bundled)", "MCP-Bench"),
    ("Safety & Refusal — Uncensor + OR-Bench, 2,250 questions", "Safety"),
    ("LongBench-v2 — Long-Context QA, 503 questions",          "LongBench-v2"),
    ("Aider Polyglot — Code Editing, 225 questions",           "Aider Polyglot"),
    ("MMMU-Pro — Multimodal MCQ, 1,200 questions",             "MMMU-Pro"),
    ("LiveBench — Meta-Benchmark, 1,436 questions (23 sub-tasks)", "LiveBench"),
    ("BenchMax Personal — Composite Score (BMS), 100 questions", "BenchMax Personal"),
    ("BenchMax Lite — All-Round, 50 questions",                  "BenchMax Lite"),
    ("BenchMax Code — Coding, 100 questions",                   "BenchMax Code"),
    ("BenchMax Reason — Reasoning, 100 questions",              "BenchMax Reason"),
    ("Writing Speed Test — Creative Writing & RP (5 prompts)", "Writing Speed Test"),
    ("Coding Speed Test — Code Generation (5 prompts)",       "Coding Speed Test"),
    ("BenchMax Tectonic — 300 questions (5 categories)",        "BenchMax Tectonic"),
    ("TruthfulQA — Truthfulness MCQ, 817 questions",           "TruthfulQA"),
]
BENCH_NAMES = [b[1] for b in BENCHMARKS]

DATASETS = {
    "HumanEval":       ("data/humaneval_full.json",       "scripts/fetch_humaneval.py"),
    "MMLU-Pro":        ("data/mmlu_pro_full.json",        "scripts/fetch_mmlu_pro.py"),
    "IFEval":          ("data/ifeval_full.json",          "scripts/fetch_ifeval.py"),
    "AIME":            ("data/aime_full.json",            "scripts/fetch_aime.py"),
    "BigCodeBench":    ("data/bigcodebench_full.json",    "scripts/fetch_bigcodebench.py"),
    "BigCodeBench-Hard": ("data/bigcodebench_hard_full.json", "scripts/fetch_bigcodebench_hard.py"),
    "BFCL":            ("data/bfcl/bfcl_full.json",       "scripts/fetch_bfcl.py"),
    "MCP-Bench":       ("data/mcp_bench/mcp_bench_full.json", "scripts/fetch_mcp_bench.py"),
    "Safety":          ("data/safety/safety_full.json",   "scripts/fetch_safety.py"),
    "Aider Polyglot":  ("data/aider_polyglot_full.json",  "scripts/fetch_aider_polyglot.py"),
    "LongBench-v2":    ("data/longbench_v2_full.json",    "scripts/fetch_longbench_v2.py"),
    "MMMU-Pro":        ("data/mmmu_pro_full.json",        "scripts/fetch_mmmu_pro.py"),
    "LiveBench":       ("data/livebench_full.json",       "scripts/fetch_livebench.py"),
    "BenchMax Personal": ("data/personal_full.json",       None),
    "BenchMax Lite":    ("data/lite_full.json",            None),
    "BenchMax Code":    ("data/code_full.json",            None),
    "BenchMax Reason":  ("data/reason_full.json",          None),
    "Writing Speed Test":   ("data/writing_speed_test_full.json",     None),
    "Coding Speed Test":    ("data/coding_speed_test_full.json",      None),
    "BenchMax Tectonic": ("data/tectonic_full.json",       None),
    "TruthfulQA":        ("data/truthfulqa_full.json",     "scripts/fetch_truthfulqa.py"),
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

DOCKER_BENCHMARKS = set()
