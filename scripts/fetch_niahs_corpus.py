"""Download Paul Graham essays as haystack corpus for the NIAHS benchmark."""
import json
import re
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"

ESSAY_INDEX_URL = "http://paulgraham.com/articles.html"
ESSAY_BASE_URL = "http://paulgraham.com/"


def strip_html(text: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_essay_links(client: httpx.Client) -> list[str]:
    resp = client.get(ESSAY_INDEX_URL)
    resp.raise_for_status()
    links = re.findall(r'href="([a-z]\w*\.html)"', resp.text)
    seen = set()
    unique = []
    for link in links:
        if link not in seen and link != "index.html":
            seen.add(link)
            unique.append(link)
    return unique


def fetch_corpus() -> str:
    print(f"Fetching essay index from {ESSAY_INDEX_URL} ...", flush=True)
    client = httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "BenchMax-NIAHS/1.0"})
    links = fetch_essay_links(client)
    print(f"  Found {len(links)} essay links.", flush=True)

    paragraphs = []
    for i, link in enumerate(links):
        url = ESSAY_BASE_URL + link
        try:
            resp = client.get(url)
            resp.raise_for_status()
            text = strip_html(resp.text)
            if len(text) > 200:
                paragraphs.append(text)
                if (i + 1) % 10 == 0:
                    print(f"  Fetched {i+1}/{len(links)} essays ({sum(len(p) for p in paragraphs):,} chars so far)...", flush=True)
        except Exception as e:
            print(f"  Warning: failed to fetch {link}: {e}", flush=True)

    client.close()
    corpus = "\n\n".join(paragraphs)
    print(f"  Total corpus: {len(corpus):,} characters (~{len(corpus)//4:,} tokens)", flush=True)
    return corpus


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    corpus = fetch_corpus()
    out_path = DATA_DIR / "niahs_corpus.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"corpus": corpus}, f, ensure_ascii=False)
    print(f"Saved corpus to {out_path}", flush=True)
