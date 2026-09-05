# BenchMax Agent Guide

> Drop this file to any local AI agent to teach it how to run LLM benchmarks via CLI.

## Quick Start

```bash
# 1. Start the server (if not already running)
py cli.py serve

# 2. Connect to LM Studio
py cli.py connect --url http://127.0.0.1:1234

# 3. Run a benchmark (full dataset by default)
py cli.py run --model MODEL_NAME --benchmark BENCHMARK_NAME --wait

# 4. Get results
py cli.py results --run-id 1 --json
```

**Global flags (apply to every command — can go before or after the subcommand):**
- `--json` — output raw JSON (machine-readable, for scripting)
- `--verbose` — show HTTP requests on stderr (debugging)
- `--yes` — skip confirmation prompts (for destructive commands)
- `--server URL` — override server URL (default: `$BENCHMAX_URL` or `http://127.0.0.1:8000`)

**Note:** Use `py` on Windows, `python3` on Linux/Mac. Or use `.venv\Scripts\python` from the project root.

---

## All Commands

### Server

| Command | What it does | Example |
|---------|-------------|---------|
| `health` | Check server is running | `py cli.py health` |
| `serve` | Start BenchMax server | `py cli.py serve --port 8000` |
| `shutdown` | Stop the server | `py cli.py shutdown` |
| `version` | Show CLI version | `py cli.py version` |

### Connection

| Command | What it does | Example |
|---------|-------------|---------|
| `connect` | Connect to LM Studio | `py cli.py connect --url http://127.0.0.1:1234` |
| `connect` | Connect to OpenAI | `py cli.py connect --url https://api.openai.com/v1 --api-key sk-...` |
| `models` | List loaded models | `py cli.py models` |

### List Resources

| Command | What it does | Example |
|---------|-------------|---------|
| `benchmarks` | List all 30 benchmarks | `py cli.py benchmarks` |
| `datasets` | Show install status | `py cli.py datasets` |

### Run a Benchmark

| Command | What it does | Example |
|---------|-------------|---------|
| `run` | Single benchmark | `py cli.py run --model deepseek-r1 --benchmark HumanEval --wait` |
| `run` | Quick test (5 samples) | `py cli.py run --model gpt-4o --benchmark MMLU-Pro --quick-test --wait` |
| `run` | Custom params | `py cli.py run --model llama-3 --benchmark IFEval --temperature 0.7 --max-tokens 4096 --wait` |

**Run options:**
- `--model` (required) — model name or ID
- `--benchmark` (required) — benchmark name (see `benchmarks`)
- `--full` — use full dataset (default, same as omitting both flags)
- `--quick-test` — use 5-sample mini dataset (fast validation)
- `--temperature` — sampling temperature (float)
- `--max-tokens` — max output tokens (default: 2048)
- `--system-prompt` — custom system prompt
- `--api-url` / `--api-key` — override connection for this run
- `--no-repetition-detection` — disable anti-loop
- `--wait` — block until done

### Batch (One Model, Multiple Benchmarks)

```bash
py cli.py batch --model deepseek-r1 --benchmarks HumanEval MMLU-Pro AIME --wait
```

### Model Queue (Multiple Models x Benchmarks)

```bash
py cli.py model-queue --models model-a model-b --benchmarks HumanEval MMLU-Pro --wait
py cli.py model-queue-halt    # stop the queue
py cli.py model-queue-skip    # skip current model
py cli.py model-queue-active  # check progress
```

### Run Control

| Command | What it does | Example |
|---------|-------------|---------|
| `status` | Check progress | `py cli.py status --run-id 1` |
| `status --wait` | Block until done | `py cli.py status --run-id 1 --wait` |
| `pause` | Pause | `py cli.py pause --run-id 1` |
| `resume` | Resume | `py cli.py resume --run-id 1` |
| `halt` | Stop permanently | `py cli.py halt --run-id 1` |
| `poll` | Live telemetry | `py cli.py poll --run-id 1` |

### Results & History

| Command | What it does | Example |
|---------|-------------|---------|
| `results` | Full results | `py cli.py results --run-id 1` |
| `results --json` | Machine-readable | `py cli.py results --run-id 1 --json` |
| `history` | All past runs | `py cli.py history` |
| `history --limit 10` | Last 10 runs | `py cli.py history --limit 10` |
| `history --model X` | Filter by model | `py cli.py history --model deepseek` |
| `history --benchmark X` | Filter by benchmark | `py cli.py history --benchmark HumanEval` |
| `history --status X` | Filter by status | `py cli.py history --status COMPLETED` |
| `diff` | Answer comparison | `py cli.py diff --run-id 1 --task-id HumanEval/0` |
| `comparison` | Compare runs | `py cli.py comparison --run-ids 1,2,3` |

### Export

```bash
py cli.py export --run-id 1 --format CSV -o results.csv
py cli.py export --run-id 1 --format JSON -o results.json
py cli.py export-batch --batch-id UUID -o batch.csv
py cli.py export-history -o all.csv
```

### Leaderboard

```bash
py cli.py leaderboard
py cli.py leaderboard-delete --run-id 1           # --yes to skip prompt
py cli.py leaderboard-clear                        # --yes to skip prompt
py cli.py leaderboard-sync --api-key YOUR_KEY
py cli.py leaderboard-settings --api-key YOUR_KEY
```

### Datasets

```bash
py cli.py install-dataset HumanEval
py cli.py install-all
py cli.py hf-token --token hf_...
py cli.py build-docker   # sandbox image for the 5 code benchmarks
```

### System

```bash
py cli.py telemetry    # CPU/RAM/GPU stats
```

---

## Available Benchmarks

| Name | Category | Questions |
|------|----------|-----------|
| `HumanEval` | Coding | 164 |
| `MMLU-Pro` | Knowledge MCQ | 12,032 |
| `IFEval` | Instruction Following | 541 |
| `AIME` | Math | 90 |
| `BigCodeBench` | Coding | 1,140 |
| `BigCodeBench-Hard` | Coding (hard) | 148 |
| `BFCL` | Function Calling | 4,696 |
| `UncensorBench` | Safety & Refusal | 150 |
| `LongBench-v2` | Long-Context QA | 503 |
| `Aider Polyglot` | Code Editing (6 langs) | 225 |
| `MMMU-Pro` | Multimodal Vision | 1,200 |
| `LiveBench` | Meta-Benchmark | 1,436 |
| `LiveCodeBench` | Live Code Gen | 175 |
| `BenchMax Personal` | Composite Score | 100 |
| `BenchMax Lite` | All-Round | 50 |
| `BenchMax Code` | Coding MCQ | 100 |
| `BenchMax Reason` | Reasoning | 100 |
| `Writing Speed Test` | Writing Speed | 5 |
| `Coding Speed Test` | Code Gen Speed | 5 |
| `BenchMax Tectonic` | 5 Categories | 300 |
| `TruthfulQA` | Truthfulness | 817 |
| `HellaSWAG` | Commonsense Reasoning | 10,042 |
| `WinoGrande` | Coreference Resolution | 1,267 |
| `ARC-Challenge` | Science Reasoning | 1,172 |
| `CommonSenseQA` | Commonsense QA | 1,221 |
| `Long Context Memory` | Memory Recall | 1,542 |
| `NIAHS` | Needle-in-Haystack | 3 (5 depths each) |
| `GAIA` | Multi-Step Reasoning | ~165 |
| `Tau3-Airline` | Agentic Tool Use | 50 |
| `BenchMax ToolCall` | Tool Use | 100 |

---

## Agent Workflows

### Benchmark a new model
```bash
py cli.py connect --url http://127.0.0.1:1234
py cli.py run --model MODEL --benchmark HumanEval --wait --json
py cli.py run --model MODEL --benchmark MMLU-Pro --wait --json
py cli.py run --model MODEL --benchmark IFEval --wait --json
py cli.py leaderboard --json
```

### Compare two models
```bash
py cli.py run --model MODEL_A --benchmark HumanEval --wait
py cli.py run --model MODEL_B --benchmark HumanEval --wait
py cli.py comparison --run-ids 1,2
```

### Quick validation (5 samples each)
```bash
py cli.py batch --model deepseek-r1 --benchmarks HumanEval MMLU-Pro IFEval --quick-test --wait
```

### Full benchmark suite
```bash
py cli.py batch --model deepseek-r1 --benchmarks HumanEval MMLU-Pro IFEval AIME BigCodeBench --wait
```

### Export for analysis
```bash
py cli.py export --run-id 1 --format CSV -o model_results.csv
py cli.py export-history --format JSON -o full_history.json
```

---

## JSON Output

Every command supports `--json`. Use this for programmatic parsing.

**Status fields:** `COMPLETED`, `FAILED`, `HALTED` (terminal). `PENDING`, `RUNNING`, `PAUSED` (in-progress).

**Run status example:**
```json
{
  "run_id": 1,
  "model_name": "deepseek-r1",
  "benchmark_name": "HumanEval",
  "status": "COMPLETED",
  "accuracy": 85.37,
  "avg_tps": 42.1,
  "avg_ttft": 0.23,
  "total_tokens": 128000
}
```

---

## Supported Providers

| Provider | URL | API Key? |
|----------|-----|----------|
| LM Studio | `http://127.0.0.1:1234/v1` | No |
| Ollama | `http://127.0.0.1:11434/v1` | No |
| OpenAI | `https://api.openai.com/v1` | Yes |
| OpenRouter | `https://openrouter.ai/api/v1` | Yes |
| Groq | `https://api.groq.com/openai/v1` | Yes |
| DeepSeek | `https://api.deepseek.com/v1` | Yes |
| AIMLAPI | `https://api.aimlapi.com/v1` | Yes |
| SiliconFlow | `https://api.siliconflow.cn/v1` | Yes |

---

## Tips

1. Start with `py cli.py health` to verify server is up
2. Use `--quick-test` for fast validation, omit it (or use `--full`) for real benchmarks
3. Use `--wait` on run/batch/model-queue to block until done (agent-friendly)
4. `--json` works anywhere: `py cli.py --json run ...` or `py cli.py run --json ...`
5. Use `--verbose` to see HTTP requests when debugging connection issues
6. Use `--yes` on destructive commands (leaderboard-clear, leaderboard-delete) to skip prompts
7. Filter history: `py cli.py history --model deepseek --status COMPLETED --limit 20`
8. Check `py cli.py status --run-id N` if a run seems stuck
9. Use `pause`/`resume` to manage long runs without losing progress
10. Export to CSV for spreadsheets, JSON for code
11. Code benchmarks use Docker sandbox (`benchmax-sandbox` — Docker-only, clear error if unavailable). Ensure Docker Desktop is running and image is built (`GET /api/docker/status`).
12. Aider Polyglot uses Docker `benchmax-sandbox` (network-allowed container) — no separate runtime download; `py cli.py build-docker` builds the image
