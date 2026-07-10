"""Helper: load HF_TOKEN from env or Token-Stuff.md."""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[1]


def ensure_hf_token():
    """Set HF_TOKEN env var if not already set. Reads from Token-Stuff.md if needed."""
    if os.environ.get("HF_TOKEN"):
        return
    ts_path = REPO_ROOT / "Token-Stuff.md"
    if ts_path.exists():
        for line in ts_path.read_text().splitlines():
            if line.startswith("HuggingFace/HF_token"):
                parts = line.split('"')
                token = parts[1] if len(parts) > 1 else None
                if token:
                    os.environ["HF_TOKEN"] = token
                    return
        logger.warning("HF_TOKEN not found in Token-Stuff.md")
