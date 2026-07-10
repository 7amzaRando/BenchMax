"""Download the BigCodeBench dataset from Hugging Face."""
import json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

try:
    from datasets import load_dataset
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token
ensure_hf_token()

def download_bigcodebench():
    print("Downloading BigCodeBench dataset from bigcode/bigcodebench (v1.2 subset)...")
    ds = load_dataset("bigcode/bigcodebench", split="v1.2", trust_remote_code=True)
    print(f"Loaded {len(ds)} samples")

    samples = []
    for i, row in enumerate(ds):
        samples.append({
            "task_id": f"BigCodeBench/{i}",
            "prompt": row["prompt"],
            "entry_point": row["entry_point"],
            "canonical_solution": row["canonical_solution"],
            "test": row["test"],
            "required_packages": row.get("required_packages", []),
        })

    full_path = DATA_DIR / "bigcodebench_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}")

    mini_path = DATA_DIR / "bigcodebench_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Updated {mini_path} with 5 samples")

    return len(samples)

if __name__ == "__main__":
    count = download_bigcodebench()
    print(f"Done. Dataset has {count} problems.")
