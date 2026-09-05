"""Download GAIA validation dataset from HuggingFace (~165 questions with public answers).

GAIA is a gated dataset — requires:
1. Accept terms at https://huggingface.co/datasets/gaia-benchmark/GAIA
2. Set HF_TOKEN environment variable or have it in Token-Stuff.md

Uses the validation split only (public ground-truth answers for local scoring).
The test set has withheld answers and is for leaderboard submission only.
"""
import json
import sys
import os
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    from datasets import load_dataset

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

# GAIA has multiple level configs. We combine all validation levels into one dataset.
# Configs: 2023_level1, 2023_level2, 2023_level3, 2024_level1, 2024_level2, 2024_level3
LEVEL_CONFIGS = [
    "2023_level1", "2023_level2", "2023_level3",
    "2024_level1", "2024_level2", "2024_level3",
]


def download_gaia():
    print("Downloading GAIA validation set (all levels)...", flush=True)

    # Ensure HF token is available
    hf_token = os.environ.get("HF_TOKEN", "")
    try:
        from _hf_token import ensure_hf_token
        ensure_hf_token()
        hf_token = hf_token or os.environ.get("HF_TOKEN", "")
    except ImportError:
        pass

    if not hf_token:
        print("WARNING: No HF_TOKEN set. GAIA is a gated dataset and requires authentication.", flush=True)
        print("  Set your token via the Connection tab or HF_TOKEN env var.", flush=True)

    samples = []
    level_counts = {}

    for config in LEVEL_CONFIGS:
        year = config[:4]
        level = config.split("_")[1]
        try:
            print(f"  Loading {config} (validation split)...", flush=True)
            ds = load_dataset("gaia-benchmark/GAIA", config, split="validation", streaming=True, token=hf_token or None)
            count = 0
            for item in ds:
                question = item.get("Question", "")
                answer = item.get("Final answer", "")
                task_id = item.get("task_id", "")
                annotator_meta = item.get("Annotator Metadata", {})
                level_val = annotator_meta.get("level", level) if isinstance(annotator_meta, dict) else level
                file_name = item.get("file_name", "")
                file_path = item.get("file_path", "")

                if not question or not answer:
                    continue

                sample = {
                    "task_id": f"gaia/{task_id}" if task_id else f"gaia/{config}_{count}",
                    "question": question,
                    "answer": str(answer).strip(),
                    "level": str(level_val),
                    "year": year,
                    "file_name": file_name,
                    "file_path": file_path,
                    "category": f"level_{level_val}",
                }
                samples.append(sample)
                count += 1

            level_counts[config] = count
            print(f"    {config}: {count} samples", flush=True)
        except Exception as e:
            print(f"    WARNING: Failed to load {config}: {e}", flush=True)
            print(f"    Make sure you accepted GAIA terms at https://huggingface.co/datasets/gaia-benchmark/GAIA", flush=True)

    if not samples:
        print("\nERROR: No samples downloaded. Possible causes:", flush=True)
        print("  1. You haven't accepted GAIA terms on HuggingFace", flush=True)
        print("  2. HF_TOKEN is not set or invalid", flush=True)
        print("  3. Network error", flush=True)
        sys.exit(1)

    # Shuffle for balanced level distribution
    import random
    random.seed(42)
    random.shuffle(samples)

    full_path = DATA_DIR / "gaia_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "gaia_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)

    print(f"\nLevel breakdown: {json.dumps(level_counts, indent=2)}", flush=True)
    return len(samples)


if __name__ == "__main__":
    count = download_gaia()
    print(f"Done. Dataset has {count} problems.", flush=True)
