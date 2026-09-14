# BenchMax v2.0

The biggest release yet. Nine new benchmarks — including BenchMax's
first agentic, multi-turn evaluations — a sandboxed code executor, a
full interface redesign, and a scriptable CLI. 21 benchmarks became 30.
~17,000 questions became ~39,500.

## Upgrading? Read this first

- **BenchMax now binds to localhost only.** If you used it from another
  device on your network, that stops working — set `BENCHMAX_HOST=0.0.0.0`
  to restore it. Single-machine users won't notice anything.
- **Code benchmarks now require Docker.** HumanEval, BigCodeBench (×2),
  LiveCodeBench, and Aider Polyglot run inside an isolated, network-off
  container instead of directly on your machine. Install Docker, then
  click **Download Runtimes** once. Everything else — 25 of 30
  benchmarks — needs nothing new.
- **House-quiz scores reset.** All six built-in quizzes were rewritten
  with harder questions and stricter grading. Lower scores are expected,
  not a bug — don't compare v2.0 runs to v1.0 runs.
- **MCP-Bench is gone.** It had no reliable ground truth to grade against.
  Use BFCL or the new BenchMax ToolCall for tool-calling instead.

**Checklist:** install Docker if you run code benchmarks → **Download
Runtimes** → **Install All** on Datasets → set `BENCHMAX_HOST` if you need
LAN access.

## Nine new benchmarks

Three are agentic — BenchMax's first benchmarks where the model doesn't
just answer one question, but works a problem over many turns: calling
tools, reading results, and adjusting its plan.

| Benchmark | Size | Tests |
|---|---|---|
| GAIA | ~165 | Research with a calculator + search tool, multi-turn |
| Tau3-Airline | 50 | Model plays support agent vs. a simulated customer, 14 tools, ≤30 turns |
| BenchMax ToolCall | 100 | Multi-call planning at a fictional company — no answer appears verbatim in the prompt |

One tests long-context memory directly:

| Benchmark | Size | Tests |
|---|---|---|
| Needle-in-a-Haystack | 3 × 5 depths | A hidden key buried at 5 depths across up to 250K tokens, with a per-depth accuracy chart |

Five round out standard reasoning coverage — HellaSWAG, WinoGrande,
ARC-Challenge, CommonSenseQA, and Long Context Memory — roughly 14,000
questions of commonsense, science, and multi-turn recall.

## A redesigned interface

- Sidebar layout, only the active tab renders, calmer visual design
- Live **Turn N/M** indicator during agentic runs
- Full conversation replay in History — see how a model solved (or
  didn't) a multi-turn task
- Results grouped by category, with a filter and per-category scores
- Inline run notes, editable from the History table
- A missing-dataset dialog that installs in one click instead of
  failing mid-run

## Harder house quizzes

All six built-in quizzes (750 questions) were rewritten for v2.0:

- Code questions require debugging real programs, not reciting definitions
- Math accepts any equivalent form (1/18 or 0.0556)
- Multi-part questions need every step right
- Hedged or fence-sitting answers no longer score

## Command line and automation

- **38 commands** covering everything the UI can do — run control,
  results, leaderboard, datasets, shutdown
- `--json` output and a `--wait` flag built for scripts and agents
- A companion agent guide documents common workflows

## Security

This release locks things down behind the scenes:

- Untrusted model code now runs isolated with no network access
- The app only talks to your own machine by default
- Every dependency was audited and updated

Nothing you need to do here — just more confidence that your models and
data stay private.

## Performance

- Large runs (10K+ questions) no longer lag the dashboard — history and
  run status now use database aggregates instead of loading every
  result into memory
- Live progress updates after every question with no extra database writes
- The anti-loop guard now confirms a real loop before intervening,
  eliminating false alarms

## Trying v2.0 first

New to BenchMax: run **BenchMax Lite** first, then **Tau3-Airline** to
watch an agent use tools across turns. Upgrading: re-run a quiz you
remember from v1.0 — the score gap is the harder grading at work, not a
regression.
