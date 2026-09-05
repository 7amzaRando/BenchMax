# BenchMax Benchmarks

30 benchmarks. Every benchmark accepts `quick_test=True` to load a mini dataset for fast validation (5 samples; NIAHS runs 3, Aider Polyglot 6 — one per language).

| Benchmark | Category | Samples | Scoring Method |
|-----------|----------|---------|----------------|
| **HumanEval** | Code generation | 164 | `safe_executor` in Docker (`benchmax-sandbox`) |
| **MMLU-Pro** | Knowledge MCQ | 12,032 | Regex letter extraction (A–J) |
| **IFEval** | Instruction following | 541 | Official google-research `INSTRUCTION_DICT` classes |
| **AIME** | Math reasoning | 90 | Multi-strategy integer extraction |
| **BigCodeBench** | Code generation | 1,140 | `safe_executor` + unittest |
| **BigCodeBench-Hard** | Code generation (hard) | 148 | Hard subset |
| **BFCL** | Function calling | 4,696 | Standalone AST checker (`bfcl_checker.py`) |
| **UncensorBench** | Refusal behaviour | 150 | Keyword matching (UncensorBench project) |
| **Aider Polyglot** | Code editing | 225 | 6 languages (Python/JS/Java/Go/Rust/C++) in Docker (`benchmax-sandbox`) |
| **LongBench-v2** | Long-context QA | 503 | MCQ letter extraction (A–D) |
| **MMMU-Pro** | Multimodal vision | 1,200 | Image + text MCQ w/ base64 PNG |
| **LiveBench** | Meta-benchmark | 1,436 | 6 categories: MCQ, math, code, language, data, instruction |
| **LiveCodeBench** | Live code generation | 175 | `check_correctness_livecodebench()` |
| **BenchMax Personal** | Composite BMS | 100 | 5-dimension weighted score (BMS out of 100) |
| **BenchMax Lite** | All-round | 50 | 4 dimensions — Code/Knowledge/Math/Logic |
| **BenchMax Code** | Coding | 100 | 4 categories — Algorithms/Data Structures/Complexity/Theory |
| **BenchMax Reason** | Reasoning | 100 | Math 60 / Logic Puzzles 30 / Data Analysis 10 |
| **BenchMax Tectonic** | Multi-category | 300 | Coding/Logic/Instruction/Knowledge/Tool Calling |
| **Writing Speed Test** | Creative writing | 5 | ~300 tokens per prompt, always correct |
| **Coding Speed Test** | Code generation | 5 | ~300 tokens per prompt, always correct |
| **TruthfulQA** | Truthfulness MCQ | 817 | A/B multiple choice |
| **HellaSWAG** | Commonsense reasoning | 10,042 | MCQ sentence completion |
| **WinoGrande** | Coreference resolution | 1,267 | MCQ pronoun resolution |
| **ARC-Challenge** | Science reasoning | 1,172 | MCQ science exam |
| **CommonSenseQA** | Commonsense QA | 1,221 | MCQ commonsense knowledge |
| **Long Context Memory** | Memory recall | 1,542 | Exact-match from LOCOMO conversations |
| **NIAHS** | Needle-in-Haystack | 3 (5 depths each, multi-needle) | Hidden key retrieval at 10/25/50/75/90% |
| **GAIA** | Multi-Step Reasoning | ~165 | Multi-turn agentic with calculator + search tools |
| **Tau3-Airline** | Agentic Tool Use | 50 | Multi-turn airline customer-service agent (14 tools, simulated user, DB-state grading) |
| **BenchMax ToolCall** | Tool Use | 100 | Multi-call company planning (chains, parallel select-all, arg traps, diagnosis, state) |

## Code execution

The 5 code benchmarks (HumanEval, BigCodeBench ×2, LiveCodeBench, Aider Polyglot) run in Docker (`benchmax-sandbox`) with a clear error if Docker is unavailable. The other 25 run host-local with no Docker.

## Datasets

Full datasets download on demand from the UI (Connection tab → dataset installer) — no manual fetching required.
