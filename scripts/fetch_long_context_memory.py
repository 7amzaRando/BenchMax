"""Download LOCOMO dataset and flatten into (context, question, answer) triples for long-context memory QA."""
import json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

LOCOMO_URL = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"


def download_long_context_memory():
    import urllib.request

    print("Downloading LOCOMO dataset...", flush=True)
    req = urllib.request.Request(LOCOMO_URL, headers={"User-Agent": "BenchMax"})
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
    conversations = json.loads(raw)
    print(f"Loaded {len(conversations)} conversations", flush=True)

    category_map = {
        1: "multi_hop",
        2: "temporal",
        3: "open_domain",
        4: "single_hop",
    }

    samples = []
    for conv_idx, conv in enumerate(conversations):
        sessions = []
        for key in sorted(conv.keys()):
            if key.startswith("session_") and not key.endswith("_date_time"):
                session_data = conv[key]
                if isinstance(session_data, list):
                    for turn in session_data:
                        if isinstance(turn, dict):
                            role = turn.get("speaker", turn.get("role", "unknown"))
                            text = turn.get("text", turn.get("content", ""))
                            if text:
                                sessions.append(f"{role}: {text}")

        context = "\n".join(sessions)

        qa_data = conv.get("qa", [])
        for qa_idx, qa in enumerate(qa_data):
            answer = qa.get("answer", "")
            question = qa.get("question", "")
            category_id = qa.get("category", 0)
            category = category_map.get(category_id, "unknown")

            if not question or not answer:
                continue

            if isinstance(answer, list):
                answer = answer[0] if answer else ""

            samples.append({
                "task_id": f"long_context_memory/{conv_idx}/{qa_idx}",
                "context": context,
                "question": question,
                "answer": str(answer).strip(),
                "category": category,
            })

        if (conv_idx + 1) % 5 == 0:
            print(f"  Processed {conv_idx + 1}/{len(conversations)} conversations, {len(samples)} QA pairs so far...", flush=True)

    full_path = DATA_DIR / "long_context_memory_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "long_context_memory_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)
    return len(samples)


if __name__ == "__main__":
    count = download_long_context_memory()
    print(f"Done. Dataset has {count} QA pairs.", flush=True)
