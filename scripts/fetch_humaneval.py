"""Download the full HumanEval dataset (164 problems) from GitHub."""
import json
import gzip
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    httpx = None

DATA_DIR = Path(__file__).parent.parent / "data"
URLS = [
    "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz",
]


def main():
    text = None
    for url in URLS:
        try:
            print(f"Downloading {url}...")
            if httpx:
                with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    raw = resp.content
            else:
                import urllib.request
                with urllib.request.urlopen(url, timeout=60) as resp:
                    raw = resp.read()
            # Decompress gzip
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
                text = f.read().decode("utf-8")
            print("Success!")
            break
        except Exception as e:
            print(f"Failed: {e}")
            continue

    if not text:
        print("ERROR: Could not download HumanEval from any source.")
        sys.exit(1)

    problems = []
    for line in text.strip().splitlines():
        if line.strip():
            problem = json.loads(line)
            problems.append(problem)

    output_path = DATA_DIR / "humaneval_full.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(problems, f, indent=2)

    print(f"Downloaded {len(problems)} HumanEval problems to {output_path}")
    sample = problems[0]
    print(f"Keys: {list(sample.keys())}")
    print(f"First task: {sample['task_id']}")
    print(f"Entry point: {sample['entry_point']}")


if __name__ == "__main__":
    main()
