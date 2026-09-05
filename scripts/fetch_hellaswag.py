"""Download HellaSWAG dataset from HuggingFace (validation split, 10,042 samples)."""
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


def download_hellaswag():
    print("Downloading HellaSWAG (validation split)...", flush=True)
    ds = load_dataset("Rowan/hellaswag", split="validation", streaming=True)
    samples = []
    for i, item in enumerate(ds):
        ctx = item.get("ctx", "")
        endings = item.get("endings", [])
        label = int(item.get("label", 0))
        if not ctx or len(endings) < 4:
            continue
        answer_letter = chr(65 + label)  # 0->A, 1->B, 2->C, 3->D
        samples.append({
            "task_id": f"hellaswag/{i}",
            "question": ctx,
            "options": endings[:4],
            "answer": answer_letter,
            "category": item.get("activity_label", "unknown"),
        })
        if len(samples) % 2000 == 0:
            print(f"  Processed {len(samples)} samples...", flush=True)

    full_path = DATA_DIR / "hellaswag_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "hellaswag_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)
    return len(samples)


if __name__ == "__main__":
    count = download_hellaswag()
    print(f"Done. Dataset has {count} problems.", flush=True)
