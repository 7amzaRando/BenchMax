"""Download the LongBench-v2 dataset from Hugging Face."""
import json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

try:
    from datasets import load_dataset
except ImportError:
    print("Installing 'datasets' package...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token
ensure_hf_token()

def download_longbench_v2():
    print("Downloading LongBench-v2 dataset from THUDM/LongBench-v2...")
    ds = load_dataset("THUDM/LongBench-v2", split="train")
    print(f"Loaded {len(ds)} samples")

    samples = []
    for i, row in enumerate(ds):
        samples.append({
            "_id": f"longbench_v2/{i}",
            "domain": row.get("domain", "unknown"),
            "sub_domain": row.get("sub_domain", "unknown"),
            "difficulty": row.get("difficulty", "unknown"),
            "length": row.get("length", "unknown"),
            "question": row["question"],
            "choice_A": row.get("choice_A", ""),
            "choice_B": row.get("choice_B", ""),
            "choice_C": row.get("choice_C", ""),
            "choice_D": row.get("choice_D", ""),
            "answer": row["answer"],
            "context": row["context"],
        })

    full_path = DATA_DIR / "longbench_v2_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}")

    mini_path = DATA_DIR / "longbench_v2_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved {min(5, len(samples))} samples to {mini_path}")

    return len(samples)

if __name__ == "__main__":
    count = download_longbench_v2()
    print(f"Done. Dataset has {count} problems.")
