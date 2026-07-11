"""Download MMMU-Pro text-only questions from Hugging Face (streaming, timeout-aware)."""
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

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token
ensure_hf_token()

def download_mmmu_pro():
    print("Downloading MMMU-Pro (standard 10 options, streaming)...", flush=True)
    import os
    # Set longer timeout for HF downloads
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "600"
    os.environ["HF_HUB_ETAG_TIMEOUT"] = "600"

    ds = load_dataset(
        "MMMU/MMMU_Pro", "standard (10 options)",
        split="test", streaming=True
    )
    samples = []
    processed = 0
    for item in ds:
        processed += 1
        question = item.get("question", "")
        options_raw = item.get("options", [])

        # Convert HF Sequence to plain Python list (critical: HF may yield a special iterable)
        options = [str(o) for o in options_raw]

        # Extract answer letter
        answer = item.get("answer", "")
        if isinstance(answer, (int, float)):
            answer = chr(65 + int(answer))
        elif isinstance(answer, str) and answer.upper() in "ABCDEFGHIJ":
            answer = answer.upper()
        else:
            answer = str(answer) if answer else ""

        # Skip image-heavy or empty samples
        if not question.strip() and not options:
            continue

        samples.append({
            "task_id": f"mmmu_pro_{len(samples)}",
            "question": question,
            "options": options,
            "answer": answer,
            "subject": item.get("subject", "unknown"),
        })
        if len(samples) % 200 == 0:
            print(f"  Processed {len(samples)} text samples (from {processed} total)...", flush=True)
        if processed >= 10000:
            break

    print(f"Loaded {len(samples)} text-only samples (processed {processed} total)", flush=True)

    full_path = DATA_DIR / "mmmu_pro_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "mmmu_pro_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)
    return len(samples)


if __name__ == "__main__":
    count = download_mmmu_pro()
    print(f"Done. Dataset has {count} problems.", flush=True)
