"""Download WinoGrande dataset from HuggingFace (test split, 1,767 samples)."""
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


def download_winogrande():
    print("Downloading WinoGrande (winogrande_xl, validation split)...", flush=True)
    ds = load_dataset("allenai/winogrande", "winogrande_xl", split="validation", streaming=True)
    samples = []
    for i, item in enumerate(ds):
        sentence = item.get("sentence", "")
        answer = item.get("answer", "")
        option1 = item.get("option1", "")
        option2 = item.get("option2", "")
        if not sentence or answer not in ("1", "2"):
            continue
        answer_letter = "A" if answer == "1" else "B"
        samples.append({
            "task_id": f"winogrande/{i}",
            "question": sentence,
            "options": [option1, option2],
            "answer": answer_letter,
        })
        if len(samples) % 500 == 0:
            print(f"  Processed {len(samples)} samples...", flush=True)

    full_path = DATA_DIR / "winogrande_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "winogrande_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)
    return len(samples)


if __name__ == "__main__":
    count = download_winogrande()
    print(f"Done. Dataset has {count} problems.", flush=True)
