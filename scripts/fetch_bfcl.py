import json, sys, os, urllib.request, re
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

MULTI_TURN_CATEGORIES = {
    "BFCL_v4_multi_turn_base.json": "multi_turn_base",
    "BFCL_v4_multi_turn_long_context.json": "multi_turn_long_context",
    "BFCL_v4_multi_turn_miss_func.json": "multi_turn_miss_func",
    "BFCL_v4_multi_turn_miss_param.json": "multi_turn_miss_param",
}


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

    gt_url_base = f"{BASE_URL}/possible_answer"
    gt_by_id = {}
    single_turn_files = [f for f in BFCL_FILES if f not in MULTI_TURN_CATEGORIES]
    for fname in single_turn_files:
        if fname == "BFCL_v4_irrelevance.json":
            continue
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

    # Multi-turn ground truth: same URL pattern, but GT is list of str lists
    mt_gt_by_id = {}
    for fname in MULTI_TURN_CATEGORIES:
        gt_url = f"{gt_url_base}/{fname}"
        try:
            with urllib.request.urlopen(gt_url, timeout=60) as resp:
                raw = resp.read().decode()
                for line in raw.strip().split("\n"):
                    if line.strip():
                        gt = json.loads(line)
                        mt_gt_by_id[gt["id"]] = gt["ground_truth"]
        except Exception:
            pass

    def _is_multi_turn(sample):
        sid = sample["id"]
        return any(sid.startswith(prefix) for prefix in ["multi_turn_base_", "multi_turn_miss_func_", "multi_turn_miss_param_", "multi_turn_long_context_"])

    def _get_mt_category(sid):
        if sid.startswith("multi_turn_base_"):
            return "multi_turn_base"
        if sid.startswith("multi_turn_miss_func_"):
            return "multi_turn_miss_func"
        if sid.startswith("multi_turn_miss_param_"):
            return "multi_turn_miss_param"
        if sid.startswith("multi_turn_long_context_"):
            return "multi_turn_long_context"
        return "multi_turn_base"

    unified = []
    for s in samples:
        sid = s["id"]

        if _is_multi_turn(s):
            category = _get_mt_category(sid)
            turns = s.get("question", [])
            ground_truth = mt_gt_by_id.get(sid, [])

            unified.append({
                "id": sid,
                "category": category,
                "question": turns,
                "function": [],
                "answer": ground_truth,
                "multi_turn": True,
                "involved_classes": s.get("involved_classes", []),
                "initial_config": s.get("initial_config", {}),
                "path": s.get("path", ""),
                "excluded_function": s.get("excluded_function", ""),
                "missed_function": s.get("missed_function", ""),
            })
        else:
            q_parts = s.get("question", [[{"role": "user", "content": ""}]])
            question_text = q_parts[0][0]["content"] if q_parts and q_parts[0] else ""

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
                "category": sid.rsplit("_", 1)[0] if "_" in sid else "unknown",
                "question": question_text,
                "function": s.get("function", []),
                "answer": expected_answer,
                "multi_turn": False,
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
