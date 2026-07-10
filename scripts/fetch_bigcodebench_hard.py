"""Download BigCodeBench-Hard dataset from Hugging Face."""
import json, os, sys
from pathlib import Path
REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token
ensure_hf_token()

try:
    from datasets import load_dataset
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    from datasets import load_dataset

def download_bigcodebench_hard():
    print("Downloading BigCodeBench-Hard (v0.1.4)...")
    ds = load_dataset("bigcode/bigcodebench-hard", split="v0.1.4")

    samples = []
    for i, row in enumerate(ds):
        samples.append({
            "task_id": f"BigCodeBench-Hard/{i}",
            "prompt": row["instruct_prompt"],
            "entry_point": row["entry_point"],
            "canonical_solution": row["canonical_solution"],
            "test": row["test"],
            "required_packages": row.get("libs", []),
        })

    full_path = DATA_DIR / "bigcodebench_hard_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}")

    mini_path = DATA_DIR / "bigcodebench_hard_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Updated {mini_path} with 5 samples")

    return len(samples)

if __name__ == "__main__":
    count = download_bigcodebench_hard()
    print(f"Done. Dataset has {count} problems.")
