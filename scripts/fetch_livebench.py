"""Download LiveBench from 6 HF categories (Parquet files)."""
import json, sys, io, urllib.request
from pathlib import Path
import pyarrow.parquet as pq
import numpy as np

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token
ensure_hf_token()

CATEGORIES = [
    "reasoning", "math", "coding", "language", "data_analysis", "instruction_following"
]

MAX_MEMORY = 100 * 1024 * 1024  # 100 MB limit per parquet file


def _to_json_safe(val):
    """Convert numpy arrays and other non-serializable types to JSON-safe values."""
    if val is None:
        return ""
    if isinstance(val, np.ndarray):
        return [str(x) for x in val.tolist()]
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return float(val)
    if isinstance(val, list):
        return [_to_json_safe(v) for v in val]
    if isinstance(val, dict):
        return {k: _to_json_safe(v) for k, v in val.items()}
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


def download_parquet(category):
    url = f"https://huggingface.co/datasets/livebench/{category}/resolve/main/data/test-00000-of-00001.parquet"
    print(f"  Downloading {category}...", end="", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "BenchMax/1.0"})
    resp = urllib.request.urlopen(req, timeout=120)
    data = resp.read()

    # Check if file is too large for memory
    if len(data) > MAX_MEMORY:
        print(f" SKIPPED ({len(data)//1024//1024}MB too large)")
        return []

    table = pq.read_table(io.BytesIO(data))
    df = table.to_pandas()
    print(f" {len(df)} rows")
    samples = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        # Extract question from 'turns' or 'question' field
        question = row.get("turns") if row.get("turns") is not None else (row.get("question") if row.get("question") is not None else "")
        if isinstance(question, list):
            parts = []
            for v in question:
                if isinstance(v, dict):
                    parts.append(str(v.get("content", v.get("role", ""))))
                else:
                    parts.append(str(v))
            question = "\n".join(parts)
        # Extract answer
        answer = row.get("answer") if row.get("answer") is not None else (row.get("ground_truth") if row.get("ground_truth") is not None else "")
        if isinstance(answer, list):
            answer = str(answer[0]) if len(answer) > 0 else ""
        if answer is None:
            answer = ""
        # Extract options
        options = row.get("options") if row.get("options") is not None else []
        if isinstance(options, dict):
            options = list(options.values())
        if options is None:
            options = []
        sample = {
            "task_id": f"livebench_{category}_{idx}",
            "category": category,
            "question": str(question),
            "options": [_to_json_safe(x) for x in options],
            "answer": str(answer),
        }
        if category == "instruction_following":
            inst_ids = row.get("instruction_ids")
            sample["instruction_ids"] = _to_json_safe(inst_ids) if inst_ids is not None else []
            kw = row.get("kwargs")
            sample["kwargs"] = _to_json_safe(kw) if kw is not None else []
        samples.append(sample)
    return samples


def download_livebench():
    all_samples = []
    for category in CATEGORIES:
        try:
            samples = download_parquet(category)
            all_samples.extend(samples)
        except Exception as e:
            print(f"  {category}: FAILED - {e}")

    print(f"\nTotal: {len(all_samples)} samples")

    full_path = DATA_DIR / "livebench_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(all_samples)} samples to {full_path}")

    mini_path = DATA_DIR / "livebench_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(all_samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}")
    return len(all_samples)


if __name__ == "__main__":
    count = download_livebench()
    print(f"Done. Dataset has {count} problems.")
