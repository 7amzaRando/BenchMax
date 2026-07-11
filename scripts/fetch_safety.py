"""Download the real Safety datasets: UncensorBench + OR-Bench."""
import json, sys, subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data" / "safety"
DATA_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token
ensure_hf_token()

def download_safety():
    # --- UncensorBench ---
    try:
        import uncensorbench
    except ImportError:
        print("Installing uncensorbench package...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uncensorbench"])
        import uncensorbench

    bench = uncensorbench.UncensorBench()
    uncensor_samples = []
    for p in bench.prompts():
        uncensor_samples.append({
            "task_id": f"uncensor_{p.id}",
            "category": "uncensor",
            "topic": p.topic,
            "subtopic": p.subtopic,
            "prompt": p.prompt,
            "expected_refusal_keywords": ["I cannot", "sorry", "I'm", "unable", "cannot", "not appropriate"],
        })
    print(f"UncensorBench: {len(uncensor_samples)} samples")

    # --- OR-Bench ---
    try:
        from datasets import load_dataset
    except ImportError:
        print("Installing datasets package...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
        from datasets import load_dataset

    or_bench_samples = []
    limits = {"or-bench-80k": 500, "or-bench-hard-1k": 1000, "or-bench-toxic": 600}
    for config_name in ["or-bench-80k", "or-bench-hard-1k", "or-bench-toxic"]:
        try:
            ds = load_dataset("bench-llm/or-bench", config_name, split="train", streaming=True)
            count = 0
            limit = limits.get(config_name, 100)
            for row in ds:
                if count >= limit:
                    break
                or_bench_samples.append({
                    "task_id": f"orbench_{config_name}_{count}",
                    "category": {                                          "or-bench-80k": "or_bench_80k",                                          "or-bench-hard-1k": "or_bench_hard",                                          "or-bench-toxic": "or_bench_toxic",                                      }[config_name],
                    "topic": row.get("category", "unknown"),
                    "prompt": row["prompt"],
                    "expected_refusal_keywords": [],
                })
                count += 1
            print(f"OR-Bench {config_name}: {count} samples")
        except Exception as e:
            print(f"  FAILED ({config_name}): {e}")

    all_samples = uncensor_samples + or_bench_samples

    full_path = DATA_DIR / "safety_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(all_samples)} samples to {full_path}")

    mini = uncensor_samples[:5] + or_bench_samples[:5]
    mini_path = DATA_DIR / "safety_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(mini, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(mini)} samples to {mini_path}")

    return len(all_samples)

if __name__ == "__main__":
    count = download_safety()
    print(f"Done. Dataset has {count} problems.")
