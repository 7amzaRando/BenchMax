"""Download ARC-Challenge dataset from HuggingFace (test split, 1,172 samples)."""
import json, sys
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    from datasets import load_dataset

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"


def download_arc():
    print("Downloading ARC-Challenge (test split)...", flush=True)
    ds = load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test", streaming=True)
    samples = []
    for i, item in enumerate(ds):
        question = item.get("question", "")
        choices = item.get("choices", {})
        answer_key = item.get("answerKey", "")
        texts = choices.get("text", [])
        labels = choices.get("label", [])
        if not question or not texts or not answer_key:
            continue
        samples.append({
            "task_id": f"arc/{i}",
            "question": question,
            "options": texts,
            "answer": answer_key,
            "category": "ARC-Challenge",
        })
        if len(samples) % 500 == 0:
            print(f"  Processed {len(samples)} samples...", flush=True)

    full_path = DATA_DIR / "arc_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "arc_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)
    return len(samples)


if __name__ == "__main__":
    count = download_arc()
    print(f"Done. Dataset has {count} problems.", flush=True)
