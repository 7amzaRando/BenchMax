"""Download the real MCP-Bench dataset from Accenture/mcp-bench on GitHub.

NOTE: The Accenture/mcp-bench repository only contains 'runner_format' task files
which do NOT include the 'tool_calls' ground truth field. The original task files with
ground truth are not publicly available. This script downloads the runner_format files
for reference but falls back to bundled samples with hand-crafted ground truth.

To regenerate the bundled ground truth, the expected tool calls must be derived
from the dependency_analysis field in each task."""
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
    # Note: runner_format files don't contain tool_calls, so correct_tool_call is null.
    # The ground truth must be extracted from dependency_analysis or set manually.
    # Until a reliable ground-truth source exists, this script does NOT overwrite
    # the data files. The benchmark falls back to hand-crafted bundled samples.
    print(f"Downloaded {len(all_tasks)} tasks from runner_format files (no tool_calls ground truth available)")
    print("Skipping data file write — benchmark falls back to bundled samples with correct ground truth")

    return len(all_tasks)

if __name__ == "__main__":
    count = download_mcp_bench()
    print(f"Done. Dataset has {count} tasks.")
