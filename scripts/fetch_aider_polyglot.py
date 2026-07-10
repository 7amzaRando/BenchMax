"""Download the full Aider Polyglot dataset (225 exercises) from GitHub."""
import json
import sys
import os
import time
import urllib.request
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_BASE = "https://raw.githubusercontent.com/Aider-AI/polyglot-benchmark/main"

# Read GitHub token from Token-Stuff.md or environment
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)
if not GITHUB_TOKEN:
    ts_path = Path(__file__).parent.parent / "Token-Stuff.md"
    if ts_path.exists():
        m = re.search(r'Github_Token\s*=\s*"([^"]+)"', ts_path.read_text())
        if m:
            GITHUB_TOKEN = m.group(1)


def _make_request(url, accept_json=False, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "BenchMax/1.0")
            if GITHUB_TOKEN:
                req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
            resp = urllib.request.urlopen(req, timeout=60)
            data = resp.read().decode("utf-8")
            return json.loads(data) if accept_json else data
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f"  Rate limited, waiting 10s...")
                time.sleep(10)
            elif attempt == retries - 1:
                print(f"  WARN: Failed to fetch {url}: {e}")
                return None
            else:
                time.sleep(2 ** attempt)
        except Exception as e:
            if attempt == retries - 1:
                print(f"  WARN: Failed to fetch {url}: {e}")
                return None
            time.sleep(2 ** attempt)
    return None


def get_all_exercises():
    """Get the exercise directory listing from GitHub API (authenticated)."""
    api_url = "https://api.github.com/repos/Aider-AI/polyglot-benchmark/git/trees/main?recursive=1"
    auth_hint = " (authenticated)" if GITHUB_TOKEN else ""
    print(f"Fetching repo tree from GitHub API{auth_hint}...")
    data = _make_request(api_url, accept_json=True)
    if not data:
        print("ERROR: Could not fetch repo tree. Check network or GitHub token.")
        sys.exit(1)
    entries = data.get("tree", [])

    exercises = {}
    for item in entries:
        p = item["path"]
        parts = p.split("/")
        if len(parts) >= 4 and parts[2] == "practice":
            lang = parts[0]
            ex_name = parts[3]
            key = f"{lang}/{ex_name}"
            if key not in exercises:
                exercises[key] = {"language": lang, "exercise": ex_name, "files": []}
            exercises[key]["files"].append("/".join(parts[4:]))

    print(f"Found {len(exercises)} exercises across {len(set(e['language'] for e in exercises.values()))} languages")
    lang_counts = {}
    for e in exercises.values():
        lang_counts[e["language"]] = lang_counts.get(e["language"], 0) + 1
    for lang, count in sorted(lang_counts.items()):
        print(f"  {lang}: {count}")
    return exercises


def fetch_text(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "BenchMax")
            resp = urllib.request.urlopen(req, timeout=30)
            return resp.read().decode("utf-8")
        except Exception as e:
            if attempt == retries - 1:
                print(f"  WARN: Failed to fetch {url}: {e}")
                return None
            time.sleep(2 ** attempt)


def fetch_exercise(lang, ex_name):
    """Fetch all relevant files for a single exercise."""
    base = f"{RAW_BASE}/{lang}/exercises/practice/{ex_name}"
    meta_base = f"{base}/.meta"
    docs_base = f"{base}/.docs"

    # Read config to find solution/test file names
    config_raw = fetch_text(f"{meta_base}/config.json")
    if not config_raw:
        print(f"  SKIP: No config for {lang}/{ex_name}")
        return None
    config = json.loads(config_raw)

    # Get instruction
    instruction = fetch_text(f"{docs_base}/instructions.md") or ""
    # Get source code (solution file)
    source_files = config.get("files", {}).get("solution", [])
    if not source_files:
        print(f"  SKIP: No solution files in config for {lang}/{ex_name}")
        return None

    source_path = source_files[0]
    source_code = fetch_text(f"{base}/{source_path}")
    if source_code is None:
        print(f"  SKIP: Could not fetch source for {lang}/{ex_name}")
        return None

    # Get test code
    test_files = config.get("files", {}).get("test", [])
    if not test_files:
        print(f"  SKIP: No test files in config for {lang}/{ex_name}")
        return None

    test_path = test_files[0]
    test_code = fetch_text(f"{base}/{test_path}")
    if test_code is None:
        print(f"  SKIP: Could not fetch test for {lang}/{ex_name}")
        return None

    # Get extra files (additional source files, build configs, etc.)
    extra_files = {}
    all_solution_files = source_files[1:]  # extra solution files beyond the main one
    for sf in all_solution_files:
        content = fetch_text(f"{base}/{sf}")
        if content:
            extra_files[sf] = content

    # Get editor/invalidator files if present
    for key in ("editor", "invalidator"):
        for f in config.get("files", {}).get(key, []):
            content = fetch_text(f"{base}/{f}")
            if content:
                extra_files[f] = content

    return {
        "task_id": f"polyglot_{lang}_{ex_name}",
        "language": lang,
        "exercise": ex_name,
        "instruction": instruction,
        "source_code": source_code,
        "source_path": source_path,
        "test_code": test_code,
        "test_path": test_path,
        "extra_files": extra_files,
        "config": config,
    }


def main():
    exercises = get_all_exercises()

    dataset = []
    skipped = 0
    for key, info in sorted(exercises.items()):
        print(f"Fetching {key}...", end=" ")
        sample = fetch_exercise(info["language"], info["exercise"])
        if sample:
            dataset.append(sample)
            print(f"OK ({len(sample['source_code'])}b src, {len(sample['test_code'])}b test)")
        else:
            skipped += 1
            print("SKIPPED")

    output_path = DATA_DIR / "aider_polyglot_full.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    print(f"\nDownloaded {len(dataset)} exercises to {output_path} ({skipped} skipped)")

    mini_path = DATA_DIR / "aider_polyglot_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(dataset[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved {min(5, len(dataset))} samples to {mini_path}")

    # Print summary
    lang_counts = {}
    for s in dataset:
        lang_counts[s["language"]] = lang_counts.get(s["language"], 0) + 1
    for lang, count in sorted(lang_counts.items()):
        print(f"  {lang}: {count}")


if __name__ == "__main__":
    main()
