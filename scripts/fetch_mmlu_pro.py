"""Download the real MMLU-Pro dataset from Hugging Face."""
import json, sys, os
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

# Try to import datasets
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

def download_mmlu_pro():
    """Downloads MMLU-Pro test split from Hugging Face."""
    print("Downloading MMLU-Pro dataset from TIGER-Lab/MMLU-Pro (test split)...")
    ds = load_dataset("TIGER-Lab/MMLU-Pro", split="test", trust_remote_code=True)
    print(f"Loaded {len(ds)} samples")

    samples = []
    for i, row in enumerate(ds):
        options = row["options"]
        # options is a list of strings
        answer_letter = chr(65 + options.index(row["answer"])) if row["answer"] in options else row["answer"]
        samples.append({
            "task_id": f"mmlu_pro/{i}",
            "question": row["question"],
            "options": options,
            "answer": answer_letter,
            "category": row.get("category", "unknown"),
        })

    full_path = DATA_DIR / "mmlu_pro_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}")

    # Update the mini file to point at more questions for dev testing
    mini_path = DATA_DIR / "mmlu_pro_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:10], f, indent=2, ensure_ascii=False)
    print(f"Updated {mini_path} with {min(10, len(samples))} samples")

    return len(samples)

if __name__ == "__main__":
    count = download_mmlu_pro()
    print(f"Done. Dataset has {count} problems.")
