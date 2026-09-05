"""Download MMMU-Pro questions AND images from Hugging Face (streaming, timeout-aware).

Writes:
  data/mmmu_pro_full.json    — 1,200 samples, each with "image_paths" (relative paths)
  data/mmmu_pro_mini.json    — first 5 samples
  data/mmmu_pro_images/*.png — one PNG per image, referenced by image_paths

The benchmark (backend/benchmarks/mmmu_pro.py) resolves image_paths against the
data/ dir, so paths are stored relative to data/, e.g. "mmmu_pro_images/test_Art_1_image_1.png".
"""
import json
import os
import sys
from io import BytesIO
from pathlib import Path

from datasets import load_dataset

REPO_ROOT = Path(__file__).parents[1]
DATA_DIR = REPO_ROOT / "data"
IMAGE_DIR = DATA_DIR / "mmmu_pro_images"

sys.path.insert(0, str(Path(__file__).parent))
from _hf_token import ensure_hf_token

ensure_hf_token()

TOTAL_TARGET = 1200  # documented MMMU-Pro "standard (10 options)" size


def _extract_png_bytes(image) -> bytes:
    """Return PNG bytes from an HF image field (dict{bytes,path} | PIL.Image | bytes)."""
    if image is None:
        return None
    if isinstance(image, dict):
        b = image.get("bytes")
        if b is not None:
            return bytes(b)
        return None
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    # PIL Image (or anything with a save() method)
    try:
        buf = BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _answer_to_letter(answer) -> str:
    if isinstance(answer, (int, float)):
        return chr(65 + int(answer))
    if isinstance(answer, str) and answer.upper() in "ABCDEFGHIJ":
        return answer.upper()
    return str(answer) if answer else ""


def download_mmmu_pro():
    print("Downloading MMMU-Pro (standard 10 options, streaming)...", flush=True)
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "600"
    os.environ["HF_HUB_ETAG_TIMEOUT"] = "600"

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    samples = []
    processed = 0
    # Test split is the documented 1,200; validation is fetched as a bonus until the
    # total target is reached (matches the on-disk dataset which mixes test_/validation_ ids).
    for split in ["test", "validation"]:
        if len(samples) >= TOTAL_TARGET:
            break
        try:
            ds = load_dataset(
                "MMMU/MMMU_Pro", "standard (10 options)",
                split=split, streaming=True,
            )
        except Exception as e:
            print(f"  SKIP split {split}: {e}", flush=True)
            continue

        for item in ds:
            processed += 1
            if len(samples) >= TOTAL_TARGET:
                break
            question = item.get("question", "")
            options_raw = item.get("options", [])
            options = [str(o) for o in options_raw]
            if not question.strip() and not options:
                continue

            item_id = str(item.get("id") or f"{split}_unknown_{len(samples)}")
            subject = item.get("subject", "unknown")

            # Save every image and record its relative path
            raw_images = item.get("image")
            image_list = raw_images if isinstance(raw_images, (list, tuple)) else [raw_images]
            image_paths = []
            for idx, img in enumerate(image_list, start=1):
                png = _extract_png_bytes(img)
                if png is None:
                    continue
                rel_name = f"mmmu_pro_images/{item_id}_image_{idx}.png"
                img_path = DATA_DIR / rel_name
                if not img_path.exists():  # do not clobber already-downloaded images
                    img_path.write_bytes(png)
                image_paths.append(rel_name.replace("/", "\\"))

            samples.append({
                "task_id": f"mmmu_pro_{len(samples)}",
                "id": item_id,
                "question": question,
                "options": options,
                "answer": _answer_to_letter(item.get("answer", "")),
                "subject": subject,
                "image_paths": image_paths,
            })
            if len(samples) % 200 == 0:
                print(f"  Processed {len(samples)} samples (from {processed} total)...", flush=True)

    print(f"Loaded {len(samples)} samples (processed {processed} total)", flush=True)

    full_path = DATA_DIR / "mmmu_pro_full.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(samples)} samples to {full_path}", flush=True)

    mini_path = DATA_DIR / "mmmu_pro_mini.json"
    with open(mini_path, "w", encoding="utf-8") as f:
        json.dump(samples[:5], f, indent=2, ensure_ascii=False)
    print(f"Saved 5 samples to {mini_path}", flush=True)

    png_count = len(list(IMAGE_DIR.glob("*.png")))
    print(f"Image dir has {png_count} PNGs in {IMAGE_DIR}", flush=True)
    return len(samples)


if __name__ == "__main__":
    count = download_mmmu_pro()
    print(f"Done. Dataset has {count} problems.", flush=True)