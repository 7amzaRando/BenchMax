"""Download TruthfulQA dataset from Hugging Face (multiple_choice config, 817 samples)."""
import json, sys, os
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    from datasets import load_dataset

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

def download_truthfulqa():
    print("Downloading TruthfulQA (multiple_choice config)...", flush=True)
    ds = load_dataset("truthfulqa/truthful_qa", "multiple_choice", split="validation", streaming=True)
    samples = []
    for item in ds:
        question = item.get("question", "")
        choices = item.get("mc1_targets", {})
        if not question or not choices or not choices.get("choices"):
            continue
        answer_idx = choices.get("labels", [0])[0]
        choice_a = choices["choices"][0]
        choice_b = choices["choices"][1] if len(choices["choices"]) > 1 else ""
        answer = "A" if answer_idx == 0 else "B"
        samples.append({
            "task_id": f"truthfulqa_{len(samples)}",
            "category": item.get("category", "unknown"),
            "type": item.get("type", "MC1"),
            "question": question,
            "choice_A": choice_a,
            "choice_B": choice_b,
            "answer": answer,
            "best_answer": choices.get("labels", [None])[0],
        })
        if len(samples) % 100 == 0:
            print(f"  Processed {len(samples)} samples...", flush=True)

    full_path = DATA_DIR / "truthfulqa_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "truthfulqa_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)
    return len(samples)

if __name__ == "__main__":
    count = download_truthfulqa()
    print(f"Done. Dataset has {count} problems.", flush=True)
