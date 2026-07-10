"""Download the real BFCL dataset from GitHub."""
import json, sys, os, urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data" / "bfcl"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BFCL_FILES = [
    "BFCL_v4_simple_python.json",
    "BFCL_v4_multiple.json",
    "BFCL_v4_parallel.json",
    "BFCL_v4_parallel_multiple.json",
    "BFCL_v4_simple_java.json",
    "BFCL_v4_simple_javascript.json",
    "BFCL_v4_irrelevance.json",
    "BFCL_v4_live_simple.json",
    "BFCL_v4_live_multiple.json",
    "BFCL_v4_live_parallel.json",
    "BFCL_v4_live_parallel_multiple.json",
    "BFCL_v4_live_irrelevance.json",
    "BFCL_v4_live_relevance.json",
    "BFCL_v4_multi_turn_base.json",
    "BFCL_v4_multi_turn_miss_func.json",
    "BFCL_v4_multi_turn_miss_param.json",
    "BFCL_v4_multi_turn_long_context.json",
    "BFCL_v4_memory.json",
    "BFCL_v4_web_search.json",
]
BASE_URL = "https://raw.githubusercontent.com/ShishirPatil/gorilla/main/berkeley-function-call-leaderboard/bfcl_eval/data"

def download_bfcl():
    samples = []
    for fname in BFCL_FILES:
        url = f"{BASE_URL}/{fname}"
        print(f"Downloading {fname}...")
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                raw = resp.read().decode()
                lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
                for line in lines:
                    samples.append(json.loads(line))
                print(f"  {len(lines)} samples")
        except Exception as e:
            print(f"  FAILED: {e}")

    # Download corresponding ground truth files
    gt_url_base = f"{BASE_URL}/possible_answer"
    gt_by_id = {}
    for fname in BFCL_FILES:
        if fname == "BFCL_v4_irrelevance.json":
            continue  # irrelevance has no ground truth
        gt_url = f"{gt_url_base}/{fname}"
        try:
            with urllib.request.urlopen(gt_url, timeout=60) as resp:
                raw = resp.read().decode()
                for line in raw.strip().split("\n"):
                    if line.strip():
                        gt = json.loads(line)
                        gt_by_id[gt["id"]] = gt["ground_truth"]
        except Exception:
            pass

    # Merge ground truth into samples and convert to BenchMax format
    unified = []
    for s in samples:
        sid = s["id"]
        cat = sid.rsplit("_", 1)[0] if "_" in sid else "unknown"
        # Convert nested question format to flat string
        q_parts = s.get("question", [[{"role": "user", "content": ""}]])
        question_text = q_parts[0][0]["content"] if q_parts and q_parts[0] else ""

        # Convert ground truth from [{func: {param: [vals]}}] to [{name, arguments}]
        expected_answer = []
        gt = gt_by_id.get(sid, [])
        for entry in gt:
            if not isinstance(entry, dict):
                continue
            for func_name, params in entry.items():
                if not isinstance(params, dict):
                    continue
                args = {}
                for pname, pvals in params.items():
                    if isinstance(pvals, list) and pvals:
                        args[pname] = next((v for v in pvals if v != ""), "")
                    else:
                        args[pname] = pvals if pvals else ""
                expected_answer.append({"name": func_name, "arguments": args})

        unified.append({
            "id": sid,
            "category": cat,
            "question": question_text,
            "function": s.get("function", []),
            "answer": expected_answer,
        })

    full_path = DATA_DIR / "bfcl_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(unified, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(unified)} samples to {full_path}")

    mini_path = DATA_DIR / "bfcl_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(unified[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved {min(5, len(unified))} samples to {mini_path}")
    return len(unified)

if __name__ == "__main__":
    count = download_bfcl()
    print(f"Done. Dataset has {count} problems.")
