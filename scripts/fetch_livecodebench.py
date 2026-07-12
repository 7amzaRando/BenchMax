"""Download the LiveCodeBench test6.jsonl dataset from HuggingFace."""
import json
import sys
import base64
import zlib
import pickle
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    httpx = None

DATA_DIR = Path(__file__).parent.parent / "data"
URL = "https://huggingface.co/datasets/livecodebench/code_generation_lite/resolve/main/test6.jsonl"


def decode_test_cases(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        decoded = base64.b64decode(raw.encode("utf-8"))
        decompressed = zlib.decompress(decoded)
        return json.loads(pickle.loads(decompressed))
    except Exception:
        return []


def main():
    text = None
    print(f"Downloading LiveCodeBench test6.jsonl...")
    if httpx:
        with httpx.Client(timeout=300.0, follow_redirects=True) as client:
            resp = client.get(URL)
            resp.raise_for_status()
            text = resp.text
    else:
        import urllib.request
        with urllib.request.urlopen(URL, timeout=300) as resp:
            text = resp.read().decode("utf-8")

    problems = []
    for line in text.strip().splitlines():
        if line.strip():
            raw = json.loads(line)
            raw["public_test_cases"] = decode_test_cases(raw.get("public_test_cases", "[]"))
            raw["private_test_cases"] = decode_test_cases(raw.get("private_test_cases", "[]"))
            all_tests = raw["public_test_cases"] + raw["private_test_cases"]
            metadata = {}
            if raw.get("metadata"):
                try:
                    metadata = json.loads(raw["metadata"]) if isinstance(raw["metadata"], str) else raw["metadata"]
                except json.JSONDecodeError:
                    metadata = {}
            raw["input_output"] = json.dumps({
                "inputs": [t["input"] for t in all_tests],
                "outputs": [t["output"] for t in all_tests],
                "fn_name": metadata.get("func_name", None),
            })
            raw["metadata"] = metadata
            problems.append(raw)

    output_path = DATA_DIR / "livecodebench_full.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(problems, f, indent=2)

    print(f"Downloaded {len(problems)} LiveCodeBench problems to {output_path}")
    if problems:
        print(f"First: {problems[0].get('question_title', 'N/A')} ({problems[0].get('difficulty', 'N/A')})")
        print(f"Test count: {len(all_tests)} ({len(raw['public_test_cases'])} public + {len(raw['private_test_cases'])} private)")


if __name__ == "__main__":
    main()
