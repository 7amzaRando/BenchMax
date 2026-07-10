"""Download the real MCP-Bench dataset from Accenture/mcp-bench on GitHub."""
import json, sys, os, urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data" / "mcp_bench"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TASK_FILES = [
    "mcpbench_tasks_single_runner_format.json",
    "mcpbench_tasks_multi_2server_runner_format.json",
    "mcpbench_tasks_multi_3server_runner_format.json",
]
BASE_URL = "https://raw.githubusercontent.com/Accenture/mcp-bench/main/tasks"

def download_mcp_bench():
    all_tasks = []
    for fname in TASK_FILES:
        url = f"{BASE_URL}/{fname}"
        print(f"Downloading {fname}...")
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                tasks = data.get("server_tasks", [])
                for t in tasks:
                    for task in t.get("tasks", []):
                        all_tasks.append(task)
                print(f"  {len(tasks)} server groups")
        except Exception as e:
            print(f"  FAILED: {e}")

    # Convert to BenchMax format
    unified = []
    for t in all_tasks:
        task_list = t.get("tasks", [])
        for task_item in task_list:
            unified.append({
                "task_id": task_item.get("task_id", f"mcp_{len(unified)}"),
                "category": t.get("combination_type", "single_server"),
                "server_count": t.get("server_count", 0),
                "available_servers": [s.get("name", "") for s in t.get("servers", [])],
                "task_description": task_item.get("fuzzy_description", task_item.get("task_description", "")),
                "conversation_history": [],
                "correct_tool_call": task_item.get("tool_calls", [{}])[0] if task_item.get("tool_calls") else None,
                "expected_answer": task_item.get("expected_answer", ""),
            })

    full_path = DATA_DIR / "mcp_bench_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(unified, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(unified)} samples to {full_path}")

    mini_path = DATA_DIR / "mcp_bench_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(unified[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved {min(5, len(unified))} samples to {mini_path}")
    return len(unified)

if __name__ == "__main__":
    count = download_mcp_bench()
    print(f"Done. Dataset has {count} tasks.")
