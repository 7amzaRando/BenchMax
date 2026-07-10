"""Download the IFEval dataset from Hugging Face."""
import json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

try:
    from datasets import load_dataset
except ImportError:
    print("Installing 'datasets' package...")
    import subprocess
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "datasets"
    ])
    from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token
ensure_hf_token()

def download_ifeval():
    print("Downloading IFEval dataset from google/IFEval (train split)...")
    ds = load_dataset("google/IFEval", split="train", trust_remote_code=True)
    print(f"Loaded {len(ds)} samples")

    samples = []
    for row in ds:
        samples.append({
            "key": row["key"],
            "prompt": row["prompt"],
            "instruction_id_list": row["instruction_id_list"],
            "kwargs": row["kwargs"],
        })

    full_path = DATA_DIR / "ifeval_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}")

    mini_path = DATA_DIR / "ifeval_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Updated {mini_path} with {min(5, len(samples))} samples")

    return len(samples)

if __name__ == "__main__":
    count = download_ifeval()
    print(f"Done. Dataset has {count} problems.")
