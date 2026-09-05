"""Download tau3-bench (sierra-research/tau2-bench) airline domain and convert to BenchMax format.

Source: https://github.com/sierra-research/tau2-bench (MIT license, vendor with attribution).
Pinned tag >= v1.0.1 (July 2026 grading update + 75+ SABER task fixes).
Uses the `base` task split (= all 50 airline tasks).

Downloads (verbatim, MIT):
  data/tau2/domains/airline/tasks.json  (50 tasks, base split)
  data/tau2/domains/airline/db.json      (base DB: flights/users/reservations)
  data/tau2/domains/airline/policy.md    (agent policy, embedded in system prompt)
  data/tau2/user_simulator/simulation_guidelines.md  (user-simulator guidelines)

Writes:
  data/taubench_airline_full.json   (50 BenchMax samples)
  data/taubench_airline_mini.json   (first 5 samples)
  data/taubench_airline_db.json     (base DB, deep-copied per sample at runtime)
  data/taubench_airline_policy.md
  data/taubench_airline_user_guidelines.md

Sample schema:
  task_id, user_scenario {persona, instructions {domain, reason_for_call,
    known_info, unknown_info, task_instructions}}, reference_actions
    [{name, arguments}], communicate_info [str], max_turns, max_wall_clock_sec,
    category
"""

import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

# Pinned upstream tag (>= v1.0.1 per ticket: grading update + SABER fixes).
TAG = "v1.0.1"
RAW = f"https://raw.githubusercontent.com/sierra-research/tau2-bench/{TAG}"

UPSTREAM_FILES = {
    f"{RAW}/data/tau2/domains/airline/tasks.json": "tasks.json",
    f"{RAW}/data/tau2/domains/airline/db.json": "db.json",
    f"{RAW}/data/tau2/domains/airline/policy.md": "policy.md",
    f"{RAW}/data/tau2/user_simulator/simulation_guidelines.md": "guidelines.md",
}

MAX_TURNS = 30
# 30 agent turns x 2 LLM calls (agent + user sim) needs a generous per-sample cap.
MAX_WALL_CLOCK_SEC = 1200


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "BenchMax/1.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _render_instructions(ins: dict | str) -> dict:
    """Normalize structured-or-string instructions to a plain dict."""
    if isinstance(ins, str):
        return {
            "domain": "airline",
            "reason_for_call": ins,
            "known_info": None,
            "unknown_info": None,
            "task_instructions": ins,
        }
    return {
        "domain": ins.get("domain", "airline"),
        "reason_for_call": ins.get("reason_for_call", ""),
        "known_info": ins.get("known_info"),
        "unknown_info": ins.get("unknown_info"),
        "task_instructions": ins.get("task_instructions", ""),
    }


def download_taubench_airline() -> int:
    print(f"Downloading tau3-bench airline domain (tag {TAG}) ...", flush=True)
    blobs = {}
    for url, name in UPSTREAM_FILES.items():
        print(f"  GET {url}", flush=True)
        blobs[name] = _get(url)
    tasks = json.loads(blobs["tasks.json"])
    db = json.loads(blobs["db.json"])
    print(f"  tasks: {len(tasks)}, db tables: {list(db.keys())}", flush=True)

    samples = []
    for t in tasks:
        crit = t.get("evaluation_criteria") or {}
        scenario = t.get("user_scenario") or {}
        samples.append({
            "task_id": f"tau3-airline/{t.get('id')}",
            "user_scenario": {
                "persona": scenario.get("persona"),
                "instructions": _render_instructions(scenario.get("instructions") or {}),
            },
            # All reference actions (incl. reads) replayed into gold DB like
            # upstream EnvironmentEvaluator (reads are harmless no-ops).
            "reference_actions": [
                {"name": a.get("name"), "arguments": a.get("arguments") or {}}
                for a in (crit.get("actions") or [])
            ],
            "communicate_info": list(crit.get("communicate_info") or []),
            "reward_basis": list(crit.get("reward_basis") or ["DB", "COMMUNICATE"]),
            "max_turns": MAX_TURNS,
            "max_wall_clock_sec": MAX_WALL_CLOCK_SEC,
            "category": "airline",
        })

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "taubench_airline_full.json", "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    with open(DATA_DIR / "taubench_airline_mini.json", "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    with open(DATA_DIR / "taubench_airline_db.json", "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)
    with open(DATA_DIR / "taubench_airline_policy.md", "w", encoding="utf-8") as f:
        f.write(blobs["policy.md"].decode("utf-8"))
    with open(DATA_DIR / "taubench_airline_user_guidelines.md", "w", encoding="utf-8") as f:
        f.write(blobs["guidelines.md"].decode("utf-8"))

    print(f"Saved {len(samples)} samples + base DB "
          f"({len(blobs['db.json']) / 1e6:.1f} MB) to {DATA_DIR}", flush=True)
    return len(samples)


if __name__ == "__main__":
    try:
        n = download_taubench_airline()
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        sys.exit(1)
    print(f"Done. Dataset has {n} tasks.", flush=True)
