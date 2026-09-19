"""Dataset scan/install, provider connect, secrets, Docker status."""

import json
import logging
import os
import subprocess
import sys
import time
import secrets
import asyncio
from pathlib import Path
from typing import List

import pandas as pd
import httpx
from sqlalchemy.orm import joinedload

from backend.config import ROOT, EXE_DIR, BENCH_NAMES, DATASETS
from backend.database import Run, get_db

from backend.ops.state import (  # noqa: E402
    _docker_daemon_running,
    _LB_SUPABASE_KEY,
    _LB_API_URL,
)
from backend.ops.bench import _make_client
from backend.ops.stats import _compute_result_stats


logger = logging.getLogger(__name__)

_dataset_scan_cache: pd.DataFrame | None = None
_dataset_scan_cache_time: float = 0.0
_DATASET_SCAN_CACHE_TTL = 30.0  # seconds

HF_TOKEN_FILE = ROOT / "records" / ".hf_token"
LB_SETTINGS_FILE = ROOT / "records" / ".lb_settings"


def _dataset_files(rel_path) -> list:
    """Normalize a DATASETS path entry (str or list of str) into a list of paths."""
    if isinstance(rel_path, (list, tuple)):
        return list(rel_path)
    return [rel_path]


def _docker_runtime_issues(benchmark_name: str, blocking: bool) -> List[dict]:
    """Probe Docker daemon + benchmax-sandbox image, return readiness issues.

    Args:
        benchmark_name: Benchmark being checked.
        blocking: True → severity "blocking" (run cannot start); False →
            severity "warning" (run starts anyway, affected slice degraded).

    Returns:
        Empty list when Docker is fully usable (or Docker checks disabled).
    """
    from backend.config import SANDBOX_USE_DOCKER
    if not SANDBOX_USE_DOCKER:
        return []
    from backend.sandbox.docker_executor import _image_exists
    daemon_running = _docker_daemon_running()
    try:
        image_built = _image_exists()
    except Exception:
        image_built = False
    if daemon_running and image_built:
        return []
    severity = "blocking" if blocking else "warning"
    if blocking:
        if not daemon_running:
            message = f"{benchmark_name} needs Docker running (start Docker Desktop first)."
        else:
            message = f"{benchmark_name} needs Docker image (click Build Docker Image)."
    else:
        missing = "Docker running" if not daemon_running else "Docker image"
        message = (
            f"{benchmark_name} coding questions need {missing} "
            f"({'start Docker Desktop' if not daemon_running else 'click Build Docker Image'}) — "
            "they will be skipped without it, other categories run normally."
        )
    return [{
        "benchmark": benchmark_name,
        "kind": "runtime",
        "severity": severity,
        "message": message,
        "action": "download_runtime",
    }]


def check_benchmark_readiness(benchmark_name: str, quick_test: bool = False) -> List[dict]:
    """Return a list of readiness issues for a benchmark.

    An empty list means the benchmark is ready to start. Each issue has keys:
    benchmark, kind (``dataset`` | ``runtime``), severity (``blocking`` |
    ``warning``), message, action (``install_dataset`` | ``download_runtime``).
    ``blocking`` issues prevent the run; ``warning`` issues (partial-Docker
    benchmarks like LiveBench) still allow it, with degraded slices.
    """
    issues: List[dict] = []

    # Datasets are only required for full runs; quick_test uses the bundled mini set.
    if not quick_test:
        entry = DATASETS.get(benchmark_name)
        if entry:
            rel_path, _ = entry
            missing = []
            for f in _dataset_files(rel_path):
                candidates = [ROOT / f, Path.cwd() / f]
                if EXE_DIR:
                    candidates.extend([EXE_DIR / f, EXE_DIR.parent / f])
                if not any(p.exists() for p in candidates):
                    missing.append(f)
            if missing:
                issues.append({
                    "benchmark": benchmark_name,
                    "kind": "dataset",
                    "severity": "blocking",
                    "message": f"The {benchmark_name} dataset is not installed (missing: {', '.join(missing)}).",
                    "action": "install_dataset",
                })

    # Docker-only benchmarks (benchmax-sandbox image + running daemon).
    # These BLOCK the run without Docker — every sample needs the sandbox.
    _DOCKER_BENCHMARKS = {
        "Aider Polyglot", "HumanEval", "BigCodeBench",
        "BigCodeBench-Hard", "LiveCodeBench",
    }
    # Partial-Docker benchmarks: only one slice needs the sandbox (LiveBench
    # coding questions via check_correctness_humaneval; the other 5 categories
    # run host-local). These WARN but never block the run.
    _DOCKER_PARTIAL_BENCHMARKS = {
        "LiveBench",
    }
    if benchmark_name in _DOCKER_BENCHMARKS:
        issues.extend(_docker_runtime_issues(benchmark_name, blocking=True))
    elif benchmark_name in _DOCKER_PARTIAL_BENCHMARKS:
        issues.extend(_docker_runtime_issues(benchmark_name, blocking=False))

    return issues


def _scan_datasets() -> pd.DataFrame:
    global _dataset_scan_cache, _dataset_scan_cache_time
    now = time.time()
    if _dataset_scan_cache is not None and (now - _dataset_scan_cache_time) < _DATASET_SCAN_CACHE_TTL:
        return _dataset_scan_cache

    import json as _json
    from backend.config import BENCHMARK_META
    rows = []
    for name, (rel_path, _) in DATASETS.items():
        files = _dataset_files(rel_path)
        sample_count = "—"
        found = True
        for f in files:
            candidates = [ROOT / f, Path.cwd() / f]
            if EXE_DIR:
                candidates.extend([EXE_DIR / f, EXE_DIR.parent / f])
            file_found = any(p.exists() for p in candidates)
            if not file_found:
                found = False
                break
            # Use static count from BENCHMARK_META when available (avoids reading 500 MB files).
            if sample_count == "—" and name in BENCHMARK_META:
                sample_count = f"{BENCHMARK_META[name]['samples']:,}"
            if sample_count == "—":
                for p in candidates:
                    if p.exists():
                        try:
                            # For small/medium files just count JSON length; for huge files this fallback is skipped above.
                            data = _json.loads(p.read_text(encoding="utf-8"))
                            sample_count = str(len(data)) if isinstance(data, list) else str(len(data.keys()))
                            # Normalise with commas
                            try:
                                sample_count = f"{int(sample_count):,}"
                            except Exception:
                                pass
                        except Exception:
                            logger.warning(f"Failed to read dataset file {p}", exc_info=True)
                            sample_count = "?"
                        break
        meta = BENCHMARK_META.get(name, {})
        rows.append({
            "Benchmark": name,
            "Installed": "✅" if found else "❌",
            "Samples": sample_count if found else "—",
            "Category": meta.get("category", "—"),
            "Docker": "🐳" if meta.get("docker") else ("◐" if meta.get("docker_partial") else ""),
            "Short": meta.get("short", ""),
        })
    result = pd.DataFrame(rows)
    _dataset_scan_cache = result
    _dataset_scan_cache_time = now
    return result


async def connect_lm_studio(api_url: str, api_key: str = "") -> tuple[str, pd.DataFrame, list, dict]:
    """Hits /v1/models (simple list) and /api/v0/models (metadata: context length) and merges them."""
    metadata = {}
    try:
        client = _make_client(api_url, api_key)
        try:
            models_raw, meta = await asyncio.gather(
                client.get_loaded_models(),
                client.get_models_metadata(),
            )
        finally:
            await client.aclose()

        if not models_raw:
            status = "Connected, but no models loaded."
            df = pd.DataFrame(columns=["id"])
            choices = []
        else:
            model_ids = [m.get("id", f"model_{i}") for i, m in enumerate(models_raw)]
            df = pd.DataFrame({"id": model_ids, "Model": model_ids})
            choices = model_ids
            status = f"Connected — {len(model_ids)} model(s) loaded."

        if meta:
            metadata = meta
            for mid in meta:
                ctx = meta[mid].get("max_context_length", "?")
                status += f"\n  {mid}: context={ctx}"
    except Exception as e:
        logger.error(f"connect_lm_studio failed: {e}", exc_info=True)
        status = f"Connection failed: {e}"
        df = pd.DataFrame(columns=["id"])
        choices = []

    return status, df, choices, metadata


PROVIDER_FILE = ROOT / "records" / ".provider.json"
DEFAULT_API_URL = "http://127.0.0.1:1234/v1"


def normalize_provider_url(raw: str) -> str:
    """Clean an LLM-provider base URL. Prepends http:// when the scheme is
    missing (the classic agent mistake that surfaces later as httpx
    "Request URL is missing an 'http://' or 'https://' protocol").

    Raises:
        ValueError: when the result still has no http(s) scheme or no host.
    """
    from urllib.parse import urlparse
    url = (raw or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    host = urlparse(url).hostname or ""

    def _host_ok(h: str) -> bool:
        if h in ("localhost",):
            return True
        if "." in h or h.startswith("["):
            return True
        try:
            import ipaddress
            ipaddress.ip_address(h)
            return True
        except ValueError:
            return False

    if urlparse(url).scheme not in ("http", "https") or not _host_ok(host):
        raise ValueError(
            f"Bad provider URL {raw!r} — use http(s)://host[:port][/v1] "
            "(e.g. http://127.0.0.1:1234/v1)."
        )
    return url


def get_default_provider() -> dict:
    """Server-side default provider. URL only — api keys are memory-only
    by security policy and are never persisted."""
    url = ""
    try:
        if PROVIDER_FILE.exists():
            url = (json.loads(PROVIDER_FILE.read_text(encoding="utf-8")) or {}).get("url", "") or ""
    except Exception:
        logger.warning(f"Failed to read provider file {PROVIDER_FILE}", exc_info=True)
    return {"url": url, "set": bool(url)}


async def set_default_provider(url: str) -> dict:
    """Validate, probe, and persist the default provider URL (key never stored)."""
    normalized = normalize_provider_url(url)
    os.makedirs(PROVIDER_FILE.parent, exist_ok=True)
    PROVIDER_FILE.write_text(json.dumps({"url": normalized}), encoding="utf-8")
    _harden_secret_file(PROVIDER_FILE)
    try:
        health = await check_provider_health(normalized)
    except Exception:
        logger.warning("Provider probe after save failed", exc_info=True)
        health = {"reachable": False, "latency_ms": None, "models_loaded": 0, "models": []}
    return {"url": normalized, **health}


def resolve_api_url(explicit: str = "") -> str:
    """Run-time provider URL: explicit per-run override, else the saved
    default, else the LM Studio default. Never returns a bare empty string,
    so httpx never sees a schemeless URL."""
    if (explicit or "").strip():
        return explicit.strip()
    return get_default_provider()["url"] or DEFAULT_API_URL


async def check_provider_health(api_url: str = "", timeout: float = 10.0) -> dict:
    """Is the LLM backend serving? Times GET <url>/models and counts models.

    Answers the "is LM Studio actually up" question without burning a run.
    Never raises — unreachable backends yield reachable=False + error text.
    """
    import time as _time
    url = resolve_api_url(api_url)
    start = _time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(f"{url.rstrip('/')}/models")
            r.raise_for_status()
            data = r.json()
        models = [m.get("id", "?") for m in data.get("data", []) if isinstance(m, dict)]
        return {"url": url, "reachable": True,
                "latency_ms": round((_time.monotonic() - start) * 1000),
                "models_loaded": len(models), "models": models}
    except Exception as e:
        return {"url": url, "reachable": False,
                "latency_ms": round((_time.monotonic() - start) * 1000),
                "models_loaded": 0, "models": [],
                "error": f"{type(e).__name__}: {e}"[:300]}


async def list_provider_models(api_url: str = "") -> dict:
    """Loaded-model IDs at the provider (default or explicit URL).

    Never raises — a dead backend yields an empty list plus error text,
    so agents can branch on it instead of catching HTTP 500s.
    """
    url = resolve_api_url(api_url)
    try:
        client = _make_client(url, "")
        try:
            models_raw = await client.get_loaded_models()
        finally:
            await client.aclose()
    except Exception as e:
        return {"url": url, "models": [],
                "error": f"{type(e).__name__}: {e}"[:300]}
    ids = [m.get("id", f"model_{i}") for i, m in enumerate(models_raw or [])]
    return {"url": url, "models": ids}


async def install_dataset(bench_name: str, hf_token: str = "") -> str:
    """Install a single benchmark dataset by running its fetch script.

    Args:
        bench_name: Benchmark name (e.g. "HumanEval", "MMLU-Pro").
        hf_token: Optional HuggingFace token for gated datasets.

    Returns:
        str: Status message with success/error details.
    """
    entry = DATASETS.get(bench_name)
    if not entry:
        return f"No dataset entry for {bench_name}."
    _, script_rel = entry
    if not script_rel:
        return f"{bench_name} does not require installation (bundled)."
    script = ROOT / script_rel
    if not script.exists():
        return f"Fetch script not found: {script}"

    env = os.environ.copy()
    if hf_token:
        env["HF_TOKEN"] = hf_token
    else:
        saved_token = _load_hf_token()
        if saved_token:
            env["HF_TOKEN"] = saved_token

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=120, env=env,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode == 0:
            global _dataset_scan_cache, _dataset_scan_cache_time
            _dataset_scan_cache = None
            return f"{bench_name} installed successfully."
        else:
            return f"Installation failed:\n{output[:500]}"
    except subprocess.TimeoutExpired:
        return f"Installation timed out for {bench_name}."
    except Exception as e:
        return f"Error: {e}"


async def install_all_missing(hf_token: str = "") -> str:
    """Install all benchmark datasets that are not yet present on disk.

    Args:
        hf_token: Optional HuggingFace token for gated datasets.

    Returns:
        str: Summary of which datasets were installed/skipped/failed.
    """
    results = []
    for name in BENCH_NAMES:
        entry = DATASETS.get(name)
        if not entry:
            continue
        rel_path, script_rel = entry
        files = _dataset_files(rel_path)
        found = True
        for f in files:
            candidates = [ROOT / f, Path.cwd() / f]
            if EXE_DIR:
                candidates.extend([EXE_DIR / f, EXE_DIR.parent / f])
            if not any(p.exists() for p in candidates):
                found = False
                break
        if found:
            continue
        status = await install_dataset(name, hf_token)
        results.append(f"{name}: {status}")
    global _dataset_scan_cache, _dataset_scan_cache_time
    _dataset_scan_cache = None
    return "\n".join(results) if results else "All datasets already installed."


async def build_docker_image() -> str:
    """Build the benchmax-sandbox Docker image with all runtimes.

    Returns:
        str: Status message with success/error details.
    """
    from backend.sandbox.docker_executor import build_image, _docker_available, _image_exists

    if not _docker_available():
        return "Docker is not available or not running. Install Docker Desktop and try again."

    if _image_exists():
        return "Docker image already built. Ready to run benchmarks."

    # Run build in thread to avoid blocking the event loop
    result = await asyncio.to_thread(build_image)
    if result["success"]:
        return "Docker image built successfully. All runtimes ready."
    else:
        return f"Docker build failed: {result.get('error', 'unknown error')}"


async def get_docker_status() -> dict:
    """Check Docker availability and image status.

    Returns:
        dict with keys: available (bool), image_exists (bool), message (str).
    """
    from backend.sandbox.docker_executor import _docker_available, _image_exists

    available = _docker_available()
    if not available:
        return {"available": False, "image_exists": False,
                "message": "Docker is not installed or not running."}

    exists = _image_exists()
    if exists:
        return {"available": True, "image_exists": True,
                "message": "Docker image ready."}
    else:
        return {"available": True, "image_exists": False,
                "message": "Docker found but image not built yet. Click 'Build Image' to create it."}


def _load_hf_token() -> str:
    if HF_TOKEN_FILE.exists():
        try:
            return HF_TOKEN_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            logger.warning(f"Failed to read HF token file {HF_TOKEN_FILE}", exc_info=True)
    return ""


def _harden_secret_file(path) -> None:
    """Best-effort 0600 on secret files (Windows ACLs: harmless no-op-ish)."""
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _save_hf_token(token: str) -> str:
    try:
        os.makedirs(HF_TOKEN_FILE.parent, exist_ok=True)
        HF_TOKEN_FILE.write_text(token.strip(), encoding="utf-8")
        _harden_secret_file(HF_TOKEN_FILE)
        return "Token saved."
    except Exception as e:
        return f"Failed to save token: {e}"


def save_lb_api_key(key: str) -> str:
    """Save the Supabase API key for online leaderboard sync.

    Args:
        key: The Supabase anon/service key.

    Returns:
        str: Status message ("Saved.").
    """
    global _LB_SUPABASE_KEY
    _LB_SUPABASE_KEY = key
    try:
        os.makedirs(LB_SETTINGS_FILE.parent, exist_ok=True)
        LB_SETTINGS_FILE.write_text(key, encoding="utf-8")
        _harden_secret_file(LB_SETTINGS_FILE)
        return "API key saved."
    except Exception as e:
        return f"Failed to save: {e}"


def load_lb_settings() -> str:
    """Load the saved Supabase API key from disk.

    Returns:
        str: The API key, or empty string if not configured.
    """
    global _LB_SUPABASE_KEY
    if not _LB_SUPABASE_KEY:
        if LB_SETTINGS_FILE.exists():
            try:
                _LB_SUPABASE_KEY = LB_SETTINGS_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                logger.warning(f"Failed to read leaderboard settings {LB_SETTINGS_FILE}", exc_info=True)
    return _LB_SUPABASE_KEY


async def sync_to_online_leaderboard(_trigger=0, api_key: str | None = None) -> str:
    """Sync local leaderboard entries to the online Supabase leaderboard.

    Args:
        _trigger: Unused (for Gradio event wiring).
        api_key: Optional override for the Supabase API key.

    Returns:
        str: Status message ("Synced N entries." or error).
    """
    try:
        key = api_key or load_lb_settings()
        if not key:
            return "No API key configured."
        with get_db() as db:
            runs = db.query(Run).options(joinedload(Run.results)).filter(Run.status.in_(["COMPLETED", "FAILED"])).order_by(Run.id.desc()).all()
            if not runs:
                return "No completed runs to sync."
            records = []
            for r in runs:
                results = r.results
                stats = _compute_result_stats(results)
                n = stats["total"]
                ok = stats["correct"]
                accuracy = stats["accuracy"]
                avg_tps = stats["avg_tps"]
                avg_ttft = stats["avg_ttft"]
                records.append({
                    "id": secrets.token_hex(8),
                    "benchmark_name": r.benchmark_name,
                    "model_name": r.model_name,
                    "accuracy": accuracy,
                    "samples": n,
                    "passed": ok,
                    "avg_tps": avg_tps,
                    "avg_ttft": avg_ttft,
                    "total_tokens": stats["total_tk"],
                    "timestamp": r.created_at.isoformat() if r.created_at else "",
                })
        headers = {
            "Content-Type": "application/json",
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        async with httpx.AsyncClient(timeout=30) as hclient:
            res = await hclient.post(
                _LB_API_URL,
                json=records,
                headers=headers,
            )
        if res.status_code in (200, 201):
            return f"Synced {len(records)} entries."
        else:
            return f"Sync failed ({res.status_code}): {res.text[:200]}"
    except Exception as e:
        return f"Sync error: {e}"
