"""Run-completion webhooks — push instead of poll.

An agent driving BenchMax unattended registers an HTTP(S) URL once; every
run that reaches a terminal state (COMPLETED / FAILED / HALTED) fires one
background POST and never blocks or breaks the run if delivery fails.

Storage is records/.webhooks.json (0600 — URLs may embed secrets).
Delivery is a daemon thread with a 10s timeout; all errors are logged,
never raised.
"""
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.config import ROOT

logger = logging.getLogger(__name__)

WEBHOOK_FILE = ROOT / "records" / ".webhooks.json"
_DELIVERY_TIMEOUT = 10.0

_lock = threading.Lock()


def _load() -> list:
    try:
        if WEBHOOK_FILE.exists():
            data = json.loads(WEBHOOK_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        logger.warning(f"Failed to read webhook file {WEBHOOK_FILE}", exc_info=True)
    return []


def _save(hooks: list) -> None:
    os.makedirs(WEBHOOK_FILE.parent, exist_ok=True)
    WEBHOOK_FILE.write_text(json.dumps(hooks, indent=2), encoding="utf-8")
    try:
        os.chmod(WEBHOOK_FILE, 0o600)
    except Exception:
        pass


def register_webhook(url: str) -> dict:
    """Register a completion webhook. Returns {id, url}."""
    url = (url or "").strip()
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(
            f"Bad webhook URL {url!r} — must be an http(s) URL "
            "(e.g. https://my-agent.example.com/benchmax-hook)."
        )
    with _lock:
        hooks = _load()
        for h in hooks:
            if h.get("url") == url:
                return {"id": h["id"], "url": url, "duplicate": True}
        hook = {"id": uuid.uuid4().hex[:12], "url": url,
                "created_at": int(time.time())}
        hooks.append(hook)
        _save(hooks)
    return {"id": hook["id"], "url": url}


def list_webhooks() -> list:
    """All registered webhooks (full URLs — this endpoint is LAN-gated)."""
    with _lock:
        return _load()


def delete_webhook(hook_id: str) -> bool:
    """Remove a webhook. Returns True when something was deleted."""
    with _lock:
        hooks = _load()
        kept = [h for h in hooks if h.get("id") != hook_id]
        if len(kept) == len(hooks):
            return False
        _save(kept)
        return True


def _deliver(url: str, payload: dict) -> None:
    try:
        with httpx.Client(timeout=_DELIVERY_TIMEOUT) as c:
            r = c.post(url, json=payload)
            logger.info(f"Webhook {urlparse(url).netloc} <- run {payload.get('run_id')} "
                        f"{payload.get('status')} (HTTP {r.status_code})")
    except Exception as e:
        logger.warning(f"Webhook delivery to {urlparse(url).netloc} failed: {e}")


def fire_run_webhook(run_id: int, status: str, model_name: str = "",
                     benchmark_name: str = "", samples_done: int = 0,
                     total_samples: int = 0) -> None:
    """Fire-and-forget completion notice. Never raises, never blocks."""
    try:
        with _lock:
            urls = [h.get("url", "") for h in _load()]
        urls = [u for u in urls if u]
        if not urls:
            return
        payload = {"event": "run.completed", "run_id": run_id, "status": status,
                   "model_name": model_name, "benchmark_name": benchmark_name,
                   "samples_done": samples_done, "total_samples": total_samples}
        for url in urls:
            threading.Thread(target=_deliver, args=(url, payload), daemon=True).start()
    except Exception:
        logger.warning("fire_run_webhook failed", exc_info=True)


def _reset_for_tests(path: Path | None = None) -> None:
    """Test helper: point the store at a tmp file (None restores default)."""
    global WEBHOOK_FILE
    WEBHOOK_FILE = path or (ROOT / "records" / ".webhooks.json")
