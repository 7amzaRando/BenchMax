# BenchMax — Benchmark Authoring Guide

## Overview

Each benchmark is a single Python file in `backend/benchmarks/` that extends `BaseBenchmark` (defined in `base.py`). The framework handles database persistence, pause/halt/resume, repetition detection, and the evaluation loop — you only need to implement dataset loading and per-sample scoring.

## Quick Start Template

```python
import re
from pathlib import Path
from backend.benchmarks.base import BaseBenchmark

class MyBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self):
        path = self.resolve_data_file("my_{suffix}.json")
        return self._load_json_cached(path)

    async def evaluate_sample(self, sample, params, model_name):
        prompt = sample["prompt"]
        gen = await self.client.generate_completion(
            prompt=prompt,
            temperature=params.get("temperature", 0.0),
            max_tokens=params.get("max_tokens", 2048),
            model_name=model_name,
        )
        answer = gen.get("answer_content", "").strip()
        expected = sample["answer"]
        correct = answer == expected
        return {
            "prompt": prompt,
            "raw_response": gen.get("raw_response"),
            "extracted_code": answer,
            "correct": correct,
            "error_message": None,
            "elapsed_time": gen.get("elapsed_time", 0.0),
            "tps": gen.get("tps", 0.0),
            "ttft": gen.get("ttft", 0.0),
            "thinking_tokens": gen.get("thinking_tokens", 0),
            "response_tokens": gen.get("response_tokens", 0),
        }
```

## 1. BaseBenchmark Contract

### Constructor
```python
def __init__(self, db: Session, client: LMStudioClient, quick_test: bool = False)
```
- `db`: SQLAlchemy session for writing `Result` rows
- `client`: `LMStudioClient` connected to the user's API endpoint
- `quick_test`: `True` loads the `_mini.json` dataset (5 samples); `False` loads `_full.json`

### Required Overrides

| Method | Returns | Purpose |
|--------|---------|---------|
| `load_dataset()` | `List[Dict]` | Load and return all samples for this benchmark |
| `evaluate_sample(sample, params, model_name)` | `Dict` | Score a single sample |

### Standard Result Dict (from `evaluate_sample`)
```python
{
    "prompt": str,           # Full prompt sent to the model
    "raw_response": str,     # Full model output (including reasoning if any)
    "extracted_code": str,   # Parsed answer / extracted code block
    "correct": bool,         # Pass/fail for this sample
    "error_message": str | None,  # Error description, or None
    "elapsed_time": float,   # Total generation time in seconds
    "tps": float,            # Tokens per second throughput
    "ttft": float,           # Time to first token in seconds
    "thinking_tokens": int,  # Reasoning/thinking tokens
    "response_tokens": int,  # Content tokens
    "scoring_details": dict | None,  # (optional) Extra scoring info stored as JSON
}
```

Any extra keys not in this set are automatically stored in the `scoring_details` JSON column.

### Optional Overrides

| Method | Purpose |
|--------|---------|
| `cleanup()` | Release resources (close files, temp dirs) after run completes/errors |
| `generate_diff(sample, result_data)` | Return an HTML diff string for the Generate Diff feature |

## 2. Dataset Format

Two JSON files per benchmark, stored in `data/`:

- `data/yourbench_full.json` — Full dataset
- `data/yourbench_mini.json` — 5-sample quick-test subset

### Sample Format
Each sample is a dict. Required keys: `task_id` (unique string identifier) and `prompt`. Other keys depend on scoring:

```json
{
    "task_id": "MyBench/0",
    "prompt": "Write a Python function...",
    "answer": "42",
    "category": "math",
    "source_code": "def foo(): ...",
    "test_suite": "assert foo(1) == 2",
    "options": ["A) True", "B) False"],
    "correct_tool_call": {"name": "get_weather", "arguments": {"city": "London"}}
}
```

### Path Resolution Pattern
In your benchmark file (3 levels deep in `backend/benchmarks/`):
```python
path = Path(__file__).parents[2] / "data" / "mybench_full.json"
```
Or use the built-in helper:
```python
self.resolve_data_file("mybench_{suffix}.json")  # suffix = "full" | "mini"
```

## 3. Scoring Patterns

### MCQ (Multiple Choice)
```python
def _score_mcq(self, response: str, options: list, answer: str) -> bool:
    # Use re.findall to extract ALL letter matches, take the last one
    # to avoid "I"/"A" false positives from prose
    import re
    matches = re.findall(r'\b([A-Z])\b', response.upper())
    if not matches:
        return False
    predicted = matches[-1]
    return predicted == answer.upper()
```

### Code Execution
```python
from backend.sandbox.safe_executor import check_correctness_humaneval
result = check_correctness_humaneval(
    entry_point=sample["entry_point"],
    prompt=sample["prompt"],
    completion=extracted_code,
    test_suite=sample["test_suite"],
    timeout=5.0,
)
correct = result["passed"]
```

### Exact Answer
```python
correct = str(extracted).strip() == str(sample["answer"]).strip()
```

### AST-based Function Call (BFCL / MCP-Bench)
```python
from backend.sandbox.bfcl_checker import ast_checker
result = ast_checker(
    func_description=sample["function"],
    model_output=model_response,
    possible_answer=sample["correct_tool_call"],
    language=...,
    test_category=...,
    model_name=model_name,
)
correct = result["valid"]
```

### Keyword/Refusal Detection (Safety)
```python
refusal_keywords = ["I cannot", "I'm sorry", "I am unable", ...]
correct = any(kw in response.lower() for kw in refusal_keywords)
```

### IFEval (Instruction Following)
```python
from backend.benchmarks.ifeval_official.instructions_registry import INSTRUCTION_DICT
cls = INSTRUCTION_DICT[sample["instruction_key"]]
kwargs = {k: sample[k] for k in cls.build_description.__code__.co_varnames[1:]
          if k in sample}
checker = cls(kwargs)
correct = checker.check_following(response)  # bool or None
```

## 4. generate_completion() Usage

```python
gen = await self.client.generate_completion(
    prompt=prompt,
    system_prompt=params.get("system_prompt"),
    temperature=params.get("temperature", 0.0),
    max_tokens=params.get("max_tokens", 2048),
    max_completion_tokens=params.get("max_tokens", 2048),  # alias of max_tokens
    stop_tokens=params.get("stop_tokens"),
    model_name=model_name,
    images=images,  # optional list of base64 PNG strings for multimodal
)
```

Returns:
```python
{
    "raw_response": "full model output including reasoning",
    "answer_content": "final answer (after <｜end▁of▁thinking｜> block)",  # or None
    "thinking_content": "reasoning block (before  response)",  # or None
    "tps": float,
    "ttft": float,
    "elapsed_time": float,
    "completion_tokens": int,
    "prompt_tokens": int,
    "reasoning_tokens": int | None,  # only if API provides it
    "thinking_tokens": int,          # estimated from ratio
    "response_tokens": int,          # estimated from ratio
    "stream_timed_out": bool,
    "_repetition_detected": bool,    # set on client instance
}
```

## 5. Registration Checklist

After creating your benchmark file and dataset JSONs, register it in 3 places:

### 1. `backend/config.py`
```python
BENCHMARKS.append(("My Benchmark", "MyBench"))
BENCH_NAMES.append("MyBench")
DATASETS["MyBench"] = {
    "suffix": "mybench",
    "desc": "Description shown in UI",
    "samples": 100,
}
```

### 2. `backend/operations.py`
Add an `elif` branch in `_instantiate_benchmark()`:
```python
elif benchmark_name == "MyBench":
    from backend.benchmarks.mybench import MyBenchmark
    bench = MyBenchmark(db, client, quick_test=quick_test)
```

### 3. `benchmax.spec` (PyInstaller build)
```python
hiddenimports=[..., "backend.benchmarks.mybench"]
datas=[..., ("data/mybench_full.json", "data"), ("data/mybench_mini.json", "data")]
```
(Or use glob patterns as the existing entries do.)

## 6. Common Patterns

### File header
```python
import re, json
from pathlib import Path
from backend.benchmarks.base import BaseBenchmark
```

### Dataset loading with fallback
```python
def load_dataset(self):
    suffix = "mini" if self.quick_test else "full"
    path = self.resolve_data_file(f"mybench_{suffix}.json")
    return self._load_json_cached(path)
```

### Code extraction from model output
```python
def _extract_code(text: str) -> str:
    import re
    m = re.search(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()
```

### Error handling
```python
try:
    gen = await self.client.generate_completion(...)
except Exception as e:
    return {"prompt": prompt, "raw_response": "", "correct": False,
            "error_message": str(e), "elapsed_time": 0.0, "tps": 0.0,
            "ttft": 0.0, "thinking_tokens": 0, "response_tokens": 0}
```

### Reasoning tokens (if not disabled)
```python
disable_reasoning = params.get("disable_reasoning", True)
gen = await self.client.generate_completion(
    ...,
    reasoning_tokens=params.get("reasoning_tokens") if not disable_reasoning else None,
)
```

## 7. Test-based Benchmarks

For code generation benchmarks, BenchMax provides two execution sandboxes:

### safe_executor (no Docker needed)
```python
from backend.sandbox.safe_executor import (
    check_correctness_humaneval,
    check_correctness_bigcodebench,
    check_correctness_livecodebench,
)
```
Uses `multiprocessing.Process` + `threading.Timer` — works on Windows, macOS, and Linux.

### Aider Polyglot (subprocess runtimes)
```python
# 6 languages (Python, JS, Java, C++, Go, Rust) via per-language
# unittest harness. Requires .runtimes/ directory (Download Runtimes button).
# See backend/benchmarks/aider_polyglot.py for the full pattern.
```

## 8. Notes

- All multi-line strings in `evaluate_sample()` return values are strings, not bytes.
- `task_id` in each sample must be unique. Convention: `"YourBench/0"`, `"YourBench/1"`, etc.
- The `_mini.json` dataset must have exactly 5 samples (`len() == 5`).
- Datasets are cached at the class level (`BaseBenchmark._dataset_cache`) — reloading the same file in the same process skips disk I/O.
- The generator has no artificial HTTP timeout — it relies on repetition detection (3 strategies) and stream timeout (60s of no tokens).
