"""Download the AIME dataset from Hugging Face (AI-MO/aimo-validation-aime)."""
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

def download_aime():
    print("Downloading AIME dataset from AI-MO/aimo-validation-aime...")
    ds = load_dataset("AI-MO/aimo-validation-aime", split="train", trust_remote_code=True)
    print(f"Loaded {len(ds)} samples")

    samples = []
    for i, row in enumerate(ds):
        samples.append({
            "task_id": f"aime/{i}",
            "problem": row["problem"],
            "answer": row["answer"],
        })

    full_path = DATA_DIR / "aime_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}")

    mini_path = DATA_DIR / "aime_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Updated {mini_path} with 5 samples")

    return len(samples)

if __name__ == "__main__":
    count = download_aime()
    print(f"Done. Dataset has {count} problems.")
