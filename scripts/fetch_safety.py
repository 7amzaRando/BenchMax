"""Download the UncensorBench dataset for under-refusal testing."""
import json
import sys
from pathlib import Path

import uncensorbench

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data" / "safety"
DATA_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token

ensure_hf_token()

def download_uncensor():
    bench = uncensorbench.UncensorBench()
    samples = []
    for p in bench.prompts():
        samples.append({
            "task_id": f"uncensor_{p.id}",
            "category": "uncensor",
            "topic": p.topic,
            "subtopic": p.subtopic,
            "prompt": p.prompt,
            "expected_refusal_keywords": ["I cannot", "sorry", "I'm", "unable", "cannot", "not appropriate"],
        })
    print(f"UncensorBench: {len(samples)} samples")

    full_path = DATA_DIR / "uncensor_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}")

    mini_path = DATA_DIR / "uncensor_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved {min(5, len(samples))} mini samples to {mini_path}")

    return len(samples)

if __name__ == "__main__":
    count = download_uncensor()
    print(f"Done. Dataset has {count} problems.")
