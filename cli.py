#!/usr/bin/env python3
"""BenchMax CLI — command-line interface for LLM benchmarking.

Wraps all 36 REST API endpoints. Requires the BenchMax server to be running
(run.bat or ``uvicorn backend.main:app --reload --port 8000``).

Usage:
    py cli.py connect --url http://127.0.0.1:1234
    py cli.py run --model qwen3.5-0.8b --benchmark HumanEval --quick-test --wait
    py cli.py results --run-id 1
"""
import argparse, json, sys, time, os, subprocess
from pathlib import Path

CLI_CONFIG = Path(__file__).parent / ".cli_config.json"
VERSION = "2.0"

try:
    import httpx
except ImportError:
    _venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    if _venv_python.exists():
        os.execv(str(_venv_python), [str(_venv_python)] + sys.argv)
    sys.exit("httpx not installed. Run: .venv\\Scripts\\pip install httpx")

DEFAULT_BASE = os.environ.get("BENCHMAX_URL", "http://127.0.0.1:8000")
_json_mode = False
_verbose_mode = False


# ── color helpers ────────────────────────────────────────────────────────────

_SUPPORTS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def _color(text, code):
    if not _SUPPORTS_COLOR or _json_mode:
        return str(text)
    return f"\033[{code}m{text}\033[0m"

def _green(t): return _color(t, "32")
def _red(t): return _color(t, "31")
def _yellow(t): return _color(t, "33")
def _dim(t): return _color(t, "2")
def _bold(t): return _color(t, "1")


# ── config ───────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if CLI_CONFIG.exists():
        try:
            return json.loads(CLI_CONFIG.read_text())
        except Exception:
            pass
    return {}


def _save_config(data: dict):
    try:
        CLI_CONFIG.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _get_saved_url() -> str:
    return _load_config().get("api_url", "")


def _get_saved_api_key() -> str:
    return _load_config().get("api_key", "")


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _client(base: str) -> httpx.Client:
    return httpx.Client(base_url=base, timeout=60.0)


def _post(c, path, body=None):
    if _verbose_mode:
        print(_dim(f"POST {path} {json.dumps(body or {}, default=str)[:200]}"), file=sys.stderr)
    r = c.post(path, json=body or {})
    if _verbose_mode:
        print(_dim(f"  -> {r.status_code} ({len(r.content)} bytes)"), file=sys.stderr)
    r.raise_for_status()
    return r.json()


def _get(c, path, params=None):
    if _verbose_mode:
        print(_dim(f"GET {path} {params or ''}"), file=sys.stderr)
    r = c.get(path, params=params)
    if _verbose_mode:
        print(_dim(f"  -> {r.status_code} ({len(r.content)} bytes)"), file=sys.stderr)
    r.raise_for_status()
    return r.json()


def _delete(c, path):
    if _verbose_mode:
        print(_dim(f"DELETE {path}"), file=sys.stderr)
    r = c.delete(path)
    if _verbose_mode:
        print(_dim(f"  -> {r.status_code}"), file=sys.stderr)
    r.raise_for_status()
    return r.json()


# ── output ───────────────────────────────────────────────────────────────────

def _out(data):
    if _json_mode:
        print(json.dumps(data, indent=2, default=str))
    else:
        _print(data)


def _print(data, indent=0):
    p = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                print(f"{p}{k}:")
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        print(f"{p}  {sk}: {sv}")
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            parts = ", ".join(f"{ik}={iv}" for ik, iv in list(item.items())[:5])
                            print(f"{p}  [{i}] {parts}")
                        else:
                            print(f"{p}  [{i}] {item}")
            elif isinstance(v, float):
                print(f"{p}{k}: {v:.2f}")
            else:
                print(f"{p}{k}: {v}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                parts = ", ".join(f"{k}={v}" for k, v in list(item.items())[:6])
                print(f"{p}[{i}] {parts}")
            else:
                print(f"{p}{item}")
    else:
        print(f"{p}{data}")


def _trunc(s, maxlen=30):
    s = str(s)
    return s if len(s) <= maxlen else s[:maxlen-2] + ".."


def _confirm(prompt, yes=False):
    if yes or _json_mode:
        return True
    resp = input(f"{prompt} [y/N] ").strip().lower()
    return resp in ("y", "yes")


def _format_eta(seconds):
    if seconds < 60:
        return f"~{int(seconds)}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"~{m}m{s:02d}s"
    else:
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        return f"~{h}h{m:02d}m"


# ── server ───────────────────────────────────────────────────────────────────

def _is_server_up(base):
    try:
        with httpx.Client(base_url=base, timeout=2.0) as c:
            return c.get("/api/health").status_code == 200
    except Exception:
        return False


def _ensure_server(base):
    if _is_server_up(base):
        return True
    port = base.rsplit(":", 1)[-1]
    print(f"Starting server on port {port}...", end="", flush=True)
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", port],
        cwd=str(Path(__file__).parent),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for i in range(20):
        time.sleep(1)
        print(".", end="", flush=True)
        if _is_server_up(base):
            print(" ready.")
            return True
    print(" failed.")
    return False


# ── polling ──────────────────────────────────────────────────────────────────

def _poll_run(client, run_id, *, interval=3.0):
    terminal = {"COMPLETED", "FAILED", "HALTED"}
    start = time.time()
    last_idx = 0
    last_time = start
    while True:
        d = _get(client, f"/api/run/{run_id}/status")
        if not isinstance(d, dict):
            return {"status": "FAILED", "error": str(d)}
        st = d.get("status", "?")
        idx, tot = d.get("current_index", 0), d.get("total_samples", 0)
        acc = d.get("accuracy_display", "?%")

        # ETA calculation based on samples/second
        now = time.time()
        eta_str = ""
        if idx > 0 and tot > 0 and idx < tot:
            elapsed = now - start
            rate = idx / elapsed if elapsed > 0 else 0
            remaining = (tot - idx) / rate if rate > 0 else 0
            eta_str = f"  {_dim(_format_eta(remaining))}"

        sys.stdout.write(f"\r  [{st}] {idx}/{tot}  {acc}{eta_str}  ")
        sys.stdout.flush()
        if st in terminal:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            return d
        time.sleep(interval)


def _poll_batch(client, batch_id, *, interval=3.0):
    start = time.time()
    while True:
        s = _get(client, f"/api/batch/{batch_id}")
        rows = s.get("summary", [])
        done = sum(1 for r in rows if r.get("Status") in ("COMPLETED", "FAILED"))
        total = len(rows)
        eta_str = ""
        if done > 0 and total > 0 and done < total:
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (total - done) / rate if rate > 0 else 0
            eta_str = f"  {_dim(_format_eta(remaining))}"
        sys.stdout.write(f"\r  Batch: {done}/{total} benchmarks{eta_str}  ")
        sys.stdout.flush()
        if done >= total and total > 0:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            return s
        time.sleep(interval)


def _poll_queue(client, *, interval=5.0):
    terminal = ("completed", "halted", "error")
    while True:
        d = _get(client, "/api/model-queue/active")
        st = d.get("status", "unknown")
        idx, tot = d.get("current_model_index", 0), d.get("total_models", 0)
        bench = d.get("current_benchmark", "")
        info = f"  {bench}" if bench else ""
        sys.stdout.write(f"\r  [{st}] {idx+1}/{tot}{info}  ")
        sys.stdout.flush()
        if st.lower() in terminal:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            return d
        time.sleep(interval)


def _show_result(data):
    st = data.get("status", "?")
    st_color = _green(st) if st == "COMPLETED" else _red(st) if st in ("FAILED", "HALTED") else st
    print(f"\n--- Run #{data.get('run_id', '?')} ---")
    _out({
        "Model": data.get("model_name", "?"),
        "Benchmark": data.get("benchmark_name", "?"),
        "Status": st_color,
        "Progress": f"{data.get('current_index', 0)}/{data.get('total_samples', 0)}",
        "Accuracy": data.get("accuracy_display", data.get("accuracy", "?")),
        "Avg TPS": data.get("avg_tps", 0),
        "Avg TTFT": data.get("avg_ttft", 0),
        "Tokens": data.get("total_tokens", 0),
    })


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_health(args):
    with _client(args.server) as c:
        d = _get(c, "/api/health")
        _out(d)


def cmd_shutdown(args):
    if not _confirm("Shutdown the server?", yes=getattr(args, "yes", False)):
        print("Aborted.")
        return
    with _client(args.server) as c:
        _out(_post(c, "/api/shutdown"))


def cmd_connect(args):
    body = {"api_url": args.url, "api_key": args.api_key or ""}
    with _client(args.server) as c:
        d = _post(c, "/api/connect", body)
        cfg = _load_config()
        cfg["api_url"] = args.url
        if args.api_key:
            cfg["api_key"] = args.api_key
        _save_config(cfg)
        _out(d)


def cmd_models(args):
    api_url = args.api_url or _get_saved_url()
    if not api_url:
        sys.exit("Error: No API URL saved. Run: py cli.py connect --url http://127.0.0.1:1234")
    with _client(args.server) as c:
        d = _post(c, "/api/connect", {"api_url": api_url, "api_key": _get_saved_api_key()})
        if _json_mode:
            _out(d.get("models", []))
            return
        models = d.get("models", [])
        if not models:
            print("No models loaded in LM Studio.")
            return
        print(f"\nLoaded models ({len(models)}):")
        for m in models:
            mid = m.get("id", "?") if isinstance(m, dict) else str(m)
            print(f"  {_bold(mid)}")
        choices = d.get("choices", [])
        if choices:
            print(f"\n  {_dim(f'{len(choices)} available for benchmarking')}")


def cmd_benchmarks(args):
    with _client(args.server) as c:
        d = _get(c, "/api/benchmarks")
        _out(d)


def cmd_datasets(args):
    with _client(args.server) as c:
        d = _get(c, "/api/datasets")
        _out(d)


def cmd_install_dataset(args):
    body = {"hf_token": args.hf_token or ""}
    with _client(args.server) as c:
        print(f"Installing {args.name}...")
        _out(_post(c, f"/api/datasets/install/{args.name}", body))


def cmd_install_all(args):
    body = {"hf_token": args.hf_token or ""}
    with _client(args.server) as c:
        print("Installing all datasets...")
        _out(_post(c, "/api/datasets/install-all", body))


def cmd_hf_token(args):
    with _client(args.server) as c:
        d = _post(c, "/api/hf-token", {"token": args.token}) if args.token else _get(c, "/api/hf-token")
        _out(d)


def _build_run_body(args, saved=None):
    saved = saved or _load_config()
    api_url = getattr(args, "api_url", "") or saved.get("api_url", "")
    api_key = getattr(args, "api_key", "") or saved.get("api_key", "")
    if not api_url:
        sys.exit("Error: No API URL saved. Run: py cli.py connect --url http://127.0.0.1:1234")
    body = {"api_url": api_url, "api_key": api_key,
            "temperature": getattr(args, "temperature", None),
            "max_tokens": getattr(args, "max_tokens", 2048),
            "system_prompt": getattr(args, "system_prompt", "") or "",
            "quick_test": getattr(args, "quick_test", False),
            "disable_repetition_detection": getattr(args, "no_repetition_detection", False)}
    return body


def cmd_run(args):
    body = _build_run_body(args)
    body["model"] = args.model
    body["benchmark"] = args.benchmark
    with _client(args.server) as c:
        d = _post(c, "/api/run/start", body)
        print(f"Run #{d.get('run_id', '?')} started: {_bold(args.model)} on {_bold(args.benchmark)}")
        if args.wait and d.get("run_id"):
            result = _poll_run(c, d["run_id"])
            _show_result(result)
        elif not _json_mode:
            _out(d)


def cmd_batch(args):
    body = _build_run_body(args)
    body["model"] = args.model
    body["benchmarks"] = args.benchmarks
    with _client(args.server) as c:
        d = _post(c, "/api/batch/start", body)
        print(f"Batch {d.get('batch_id', '?')[:8]} started: {_bold(args.model)} on {', '.join(args.benchmarks)}")
        if args.wait and d.get("batch_id"):
            _out(_poll_batch(c, d["batch_id"]))
        elif not _json_mode:
            _out(d)


def cmd_model_queue(args):
    body = _build_run_body(args)
    body["models"] = args.models
    body["benchmarks"] = args.benchmarks
    with _client(args.server) as c:
        d = _post(c, "/api/model-queue/start", body)
        print(f"Model queue {d.get('queue_id', '?')[:8]} started")
        if args.wait and d.get("queue_id"):
            _out(_poll_queue(c))
        elif not _json_mode:
            _out(d)


def cmd_model_queue_active(args):
    with _client(args.server) as c:
        _out(_get(c, "/api/model-queue/active"))


def cmd_model_queue_halt(args):
    with _client(args.server) as c:
        _out(_post(c, "/api/model-queue/halt"))


def cmd_model_queue_skip(args):
    with _client(args.server) as c:
        _out(_post(c, "/api/model-queue/skip"))


def cmd_status(args):
    rid = args.run_id
    with _client(args.server) as c:
        if args.wait:
            result = _poll_run(c, rid)
            _show_result(result)
        else:
            d = _get(c, f"/api/run/{rid}/status")
            _out(d)


def cmd_poll(args):
    with _client(args.server) as c:
        _out(_get(c, "/api/poll", {"active_run_id": args.run_id or 0}))


def cmd_results(args):
    rid = args.run_id
    with _client(args.server) as c:
        d = _get(c, f"/api/runs/{rid}")
        if _json_mode:
            _out(d)
            return
        summary = d.get("summary", {})
        print(f"\n--- Run #{rid} ---")
        _out(summary)
        samples = d.get("samples", [])
        if samples:
            print(f"\nSamples ({len(samples)}):")
            for s in samples:
                correct = s.get("Correct")
                status = _green("PASS") if correct else _red("FAIL")
                tps = f"{s.get('TPS', 0):.1f} tps" if s.get("TPS") else ""
                tokens = s.get("Tokens", "")
                print(f"  [{status}] {s.get('Task ID', '?')}  {tps}  {tokens} tokens")


def cmd_history(args):
    with _client(args.server) as c:
        params = {}
        if args.limit:
            params["limit"] = args.limit
        d = _get(c, "/api/runs", params)
        if _json_mode:
            _out(d)
            return
        runs = d.get("runs", [])

        # Client-side filtering
        if args.model:
            runs = [r for r in runs if args.model.lower() in r.get("Model", "").lower()]
        if args.benchmark:
            runs = [r for r in runs if args.benchmark.lower() in r.get("Benchmark", "").lower()]
        if args.status:
            runs = [r for r in runs if args.status.upper() == r.get("Status", "").upper()]

        total = d.get("total", len(runs))
        if not runs:
            print("No runs found.")
            return
        shown = len(runs)
        label = f"{shown}/{total}" if total > shown else str(total)
        print(f"\nHistory ({label} runs):")
        print(f"  {'ID':>5}  {'Status':<10}  {'Model':<30}  {'Benchmark':<20}  {'Accuracy':<10}")
        print(f"  {'-'*5}  {'-'*10}  {'-'*30}  {'-'*20}  {'-'*10}")
        for r in runs:
            st = r.get("Status", "?")
            if st == "COMPLETED":
                st_display = _green(st)
            elif st in ("FAILED", "HALTED"):
                st_display = _red(st)
            elif st == "RUNNING":
                st_display = _yellow(st)
            else:
                st_display = st
            print(f"  {r.get('Run ID', '?'):>5}  {st_display:<10}  {_trunc(r.get('Model', '?'), 30):<30}  {_trunc(r.get('Benchmark', '?'), 20):<20}  {r.get('Accuracy', '?'):<10}")


def cmd_diff(args):
    with _client(args.server) as c:
        d = _get(c, f"/api/runs/{args.run_id}/diff/{args.task_id}")
        _out(d)


def cmd_comparison(args):
    with _client(args.server) as c:
        _out(_get(c, "/api/comparison", {"run_ids": args.run_ids}))


def cmd_export(args):
    fmt = args.format or "CSV"
    with _client(args.server) as c:
        r = c.get(f"/api/export/runs/{args.run_id}", params={"format": fmt}, follow_redirects=True)
        r.raise_for_status()
        fname = args.output or f"run_{args.run_id}.{fmt.lower()}"
        Path(fname).write_bytes(r.content)
        print(f"Exported {fname} ({len(r.content):,} bytes)")


def cmd_export_batch(args):
    fmt = args.format or "CSV"
    with _client(args.server) as c:
        r = c.get(f"/api/export/batch/{args.batch_id}", params={"format": fmt}, follow_redirects=True)
        r.raise_for_status()
        fname = args.output or f"batch_{args.batch_id}.{fmt.lower()}"
        Path(fname).write_bytes(r.content)
        print(f"Exported {fname} ({len(r.content):,} bytes)")


def cmd_export_history(args):
    fmt = args.format or "CSV"
    with _client(args.server) as c:
        r = c.get("/api/export/history", params={"format": fmt}, follow_redirects=True)
        r.raise_for_status()
        fname = args.output or f"history.{fmt.lower()}"
        Path(fname).write_bytes(r.content)
        print(f"Exported {fname} ({len(r.content):,} bytes)")


def cmd_batch_status(args):
    with _client(args.server) as c:
        _out(_get(c, f"/api/batch/{args.batch_id}"))


def cmd_leaderboard(args):
    with _client(args.server) as c:
        d = _get(c, "/api/leaderboard")
        if _json_mode:
            _out(d)
            return
        lb = d.get("leaderboard", [])
        if not lb:
            print("Leaderboard is empty.")
            return
        print(f"\nLeaderboard ({len(lb)} entries):")
        print(f"  {'ID':>5}  {'Model':<30}  {'Benchmark':<20}  {'Accuracy':<10}  {'Date':<12}")
        print(f"  {'-'*5}  {'-'*30}  {'-'*20}  {'-'*10}  {'-'*12}")
        for e in lb:
            print(f"  {e.get('Run ID', '?'):>5}  {_trunc(e.get('Model', '?'), 30):<30}  {_trunc(e.get('Benchmark', '?'), 20):<20}  {e.get('Accuracy', '?'):<10}  {e.get('Date', '?')}")


def cmd_leaderboard_delete(args):
    if not _confirm(f"Delete run #{args.run_id} from leaderboard?", yes=getattr(args, "yes", False)):
        print("Aborted.")
        return
    with _client(args.server) as c:
        _out(_delete(c, f"/api/leaderboard/{args.run_id}"))


def cmd_leaderboard_clear(args):
    if not _confirm("Clear entire leaderboard?", yes=getattr(args, "yes", False)):
        print("Aborted.")
        return
    with _client(args.server) as c:
        _out(_post(c, "/api/leaderboard/clear", {"confirm_text": "CONFIRM"}))


def cmd_leaderboard_sync(args):
    with _client(args.server) as c:
        _out(_post(c, "/api/leaderboard/sync", {"api_key": args.api_key or ""}))


def cmd_leaderboard_settings(args):
    with _client(args.server) as c:
        d = _post(c, "/api/leaderboard/settings", {"api_key": args.api_key}) if args.api_key else _get(c, "/api/leaderboard/settings")
        _out(d)


def cmd_telemetry(args):
    with _client(args.server) as c:
        d = _get(c, "/api/telemetry")
        if _json_mode:
            _out(d)
            return
        gpu = d.get("gpu_name", "N/A") if d.get("gpu_available") else "N/A"
        print(f"\n--- System Telemetry ---")
        _out({
            "CPU": f"{d.get('cpu_percent', 0):.1f}%",
            "RAM": f"{d.get('ram_used_gb', 0):.1f}/{d.get('ram_total_gb', 0):.1f} GB ({d.get('ram_percent', 0):.1f}%)",
            "GPU": gpu,
            "GPU Load": f"{d.get('gpu_load', 0):.1f}%",
            "VRAM": f"{d.get('vram_used_mb', 0):.0f}/{d.get('vram_total_mb', 0):.0f} MB ({d.get('vram_percent', 0):.1f}%)",
        })


def cmd_pause(args):
    with _client(args.server) as c:
        _out(_post(c, f"/api/run/{args.run_id}/pause"))


def cmd_resume(args):
    saved = _load_config()
    body = {"api_url": args.api_url or saved.get("api_url", ""),
            "api_key": args.api_key or saved.get("api_key", ""),
            "temperature": args.temperature, "max_tokens": args.max_tokens,
            "system_prompt": args.system_prompt or ""}
    if not body["api_url"]:
        sys.exit("Error: No API URL saved. Run: py cli.py connect --url http://127.0.0.1:1234")
    with _client(args.server) as c:
        _out(_post(c, f"/api/run/{args.run_id}/resume", body))


def cmd_halt(args):
    with _client(args.server) as c:
        _out(_post(c, f"/api/run/{args.run_id}/halt"))


def cmd_serve(args):
    port, host = args.port or 8000, args.host or "127.0.0.1"
    print(f"Starting BenchMax on {host}:{port}...")
    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "backend.main:app",
                               "--reload", "--host", host, "--port", str(port)])


def cmd_build_docker(args):
    with _client(args.server) as c:
        print("Building Docker image...")
        _out(_post(c, "/api/docker/build"))


def cmd_docker_status(args):
    with _client(args.server) as c:
        _out(_get(c, "/api/docker/status"))


def cmd_version(args):
    print(f"BenchMax CLI v{VERSION}")


# ── parser ───────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="benchmax",
        description="BenchMax CLI — LLM benchmarking from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  health                        Check server status
  connect --url URL             Connect to LM Studio / OpenAI-compatible API
  models                        List loaded models
  benchmarks                    List all benchmarks
  datasets                      Show dataset install status
  run --model M --benchmark B   Run a single benchmark
  batch --model M --benchmarks  Run multiple benchmarks on one model
  model-queue --models M1 M2    Run benchmarks across multiple models
  status --run-id N             Check run progress
  results --run-id N            Show run results
  history                       List all past runs
  pause/resume/halt --run-id N  Control a running benchmark
  export --run-id N             Export results to CSV/JSON
  leaderboard                   View leaderboard
  telemetry                     Show CPU/RAM/GPU stats
  build-docker                  Build Docker sandbox image
  docker-status                 Check Docker availability
  serve --port 8000             Start the server
  version                       Show CLI version

global flags:
  --json                        Machine-readable JSON output
  --verbose                     Show HTTP requests on stderr
  --server URL                  Override server address (default: http://127.0.0.1:8000)
  --yes                         Skip confirmation prompts

examples:
  py cli.py connect --url http://127.0.0.1:1234
  py cli.py run --model qwen3.5-0.8b --benchmark HumanEval --quick-test --wait
  py cli.py batch --model deepseek-r1 --benchmarks HumanEval MMLU-Pro --wait
  py cli.py history --json
  py cli.py history --model deepseek --status COMPLETED
""")
    p.add_argument("--server", default=DEFAULT_BASE, help="Server URL")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--verbose", action="store_true", help="Show HTTP requests")
    p.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    sub = p.add_subparsers(dest="command")

    # Common parent so --json/--verbose/--yes work in any position
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--verbose", action="store_true")
    common.add_argument("--yes", action="store_true")

    sub.add_parser("health", parents=[common], help="Check server status")
    sd = sub.add_parser("shutdown", parents=[common], help="Stop the server")
    sv = sub.add_parser("serve", parents=[common], help="Start the server")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--host", default="0.0.0.0")

    cn = sub.add_parser("connect", parents=[common], help="Connect to LM Studio / API")
    cn.add_argument("--url", required=True)
    cn.add_argument("--api-key", default="")

    md = sub.add_parser("models", parents=[common], help="List loaded models")
    md.add_argument("--api-url", default="", help="Override API URL")

    sub.add_parser("benchmarks", parents=[common], help="List all benchmarks")
    sub.add_parser("datasets", parents=[common], help="Show dataset install status")

    di = sub.add_parser("install-dataset", parents=[common], help="Install a dataset")
    di.add_argument("name")
    di.add_argument("--hf-token", default="")
    diall = sub.add_parser("install-all", parents=[common], help="Install all datasets")
    diall.add_argument("--hf-token", default="")
    hft = sub.add_parser("hf-token", parents=[common], help="Get/set HuggingFace token")
    hft.add_argument("--token", default="")

    # run
    run_p = sub.add_parser("run", parents=[common], help="Run a single benchmark")
    run_p.add_argument("--model", required=True, help="Model name or ID")
    run_p.add_argument("--benchmark", required=True, help="Benchmark name")
    run_p.add_argument("--api-url", default="", help="Override API URL for this run")
    run_p.add_argument("--api-key", default="", help="Override API key for this run")
    run_p.add_argument("--temperature", type=float, default=None)
    run_p.add_argument("--max-tokens", type=int, default=2048)
    run_p.add_argument("--system-prompt", default="")
    run_p.add_argument("--quick-test", action="store_true", default=False, help="Use 5-sample mini dataset")
    run_p.add_argument("--full", action="store_true", help="Use full dataset (default)")
    run_p.add_argument("--no-repetition-detection", action="store_true")
    run_p.add_argument("--wait", action="store_true", help="Block until done")

    # batch
    batch_p = sub.add_parser("batch", parents=[common], help="Run multiple benchmarks on one model")
    batch_p.add_argument("--model", required=True, help="Model name or ID")
    batch_p.add_argument("--benchmarks", nargs="+", required=True, help="Benchmark names")
    batch_p.add_argument("--api-url", default="", help="Override API URL for this run")
    batch_p.add_argument("--api-key", default="", help="Override API key for this run")
    batch_p.add_argument("--temperature", type=float, default=None)
    batch_p.add_argument("--max-tokens", type=int, default=2048)
    batch_p.add_argument("--system-prompt", default="")
    batch_p.add_argument("--quick-test", action="store_true", default=False, help="Use 5-sample mini dataset")
    batch_p.add_argument("--full", action="store_true", help="Use full dataset (default)")
    batch_p.add_argument("--no-repetition-detection", action="store_true")
    batch_p.add_argument("--wait", action="store_true", help="Block until done")

    # model-queue
    mq_p = sub.add_parser("model-queue", parents=[common], help="Run benchmarks across multiple models")
    mq_p.add_argument("--models", nargs="+", required=True, help="Model names")
    mq_p.add_argument("--benchmarks", nargs="+", required=True, help="Benchmark names")
    mq_p.add_argument("--api-url", default="", help="Override API URL for this run")
    mq_p.add_argument("--api-key", default="", help="Override API key for this run")
    mq_p.add_argument("--temperature", type=float, default=None)
    mq_p.add_argument("--max-tokens", type=int, default=2048)
    mq_p.add_argument("--system-prompt", default="")
    mq_p.add_argument("--quick-test", action="store_true", default=False, help="Use 5-sample mini dataset")
    mq_p.add_argument("--full", action="store_true", help="Use full dataset (default)")
    mq_p.add_argument("--no-repetition-detection", action="store_true")
    mq_p.add_argument("--wait", action="store_true", help="Block until done")

    st = sub.add_parser("status", parents=[common], help="Check run progress")
    st.add_argument("--run-id", type=int, required=True)
    st.add_argument("--wait", action="store_true", help="Block until done")

    pl = sub.add_parser("poll", parents=[common], help="Poll live telemetry")
    pl.add_argument("--run-id", type=int, default=0)

    sub.add_parser("model-queue-active", parents=[common], help="Check model queue status")
    sub.add_parser("model-queue-halt", parents=[common], help="Halt model queue")
    sub.add_parser("model-queue-skip", parents=[common], help="Skip current model in queue")

    pa = sub.add_parser("pause", parents=[common], help="Pause a run")
    pa.add_argument("--run-id", type=int, required=True)
    re = sub.add_parser("resume", parents=[common], help="Resume a run")
    re.add_argument("--run-id", type=int, required=True)
    re.add_argument("--api-url", default="")
    re.add_argument("--api-key", default="")
    re.add_argument("--temperature", type=float, default=None)
    re.add_argument("--max-tokens", type=int, default=None)
    re.add_argument("--system-prompt", default="")
    ha = sub.add_parser("halt", parents=[common], help="Halt a run")
    ha.add_argument("--run-id", type=int, required=True)

    res = sub.add_parser("results", parents=[common], help="Show run results")
    res.add_argument("--run-id", type=int, required=True)

    hist = sub.add_parser("history", parents=[common], help="List all past runs")
    hist.add_argument("--limit", type=int, default=0, help="Max runs to show (0=all)")
    hist.add_argument("--model", default="", help="Filter by model name")
    hist.add_argument("--benchmark", default="", help="Filter by benchmark name")
    hist.add_argument("--status", default="", help="Filter by status (COMPLETED, FAILED, etc)")

    df = sub.add_parser("diff", parents=[common], help="Show answer diff")
    df.add_argument("--run-id", type=int, required=True)
    df.add_argument("--task-id", required=True)

    cmp = sub.add_parser("comparison", parents=[common], help="Compare runs")
    cmp.add_argument("--run-ids", required=True, help="Comma-separated run IDs")

    for name in ("export", "export-batch", "export-history"):
        pr = sub.add_parser(name, parents=[common])
        if name != "export-history":
            pr.add_argument("--run-id" if name == "export" else "--batch-id", required=True)
        pr.add_argument("--format", choices=["CSV", "JSON"], default="CSV")
        pr.add_argument("--output", "-o", default="")

    bs = sub.add_parser("batch-status", parents=[common], help="Check batch status")
    bs.add_argument("--batch-id", required=True)

    sub.add_parser("leaderboard", parents=[common], help="View leaderboard")
    ld = sub.add_parser("leaderboard-delete", parents=[common], help="Delete from leaderboard")
    ld.add_argument("--run-id", type=int, required=True)
    lc = sub.add_parser("leaderboard-clear", parents=[common], help="Clear leaderboard")
    ls = sub.add_parser("leaderboard-sync", parents=[common], help="Sync leaderboard online")
    ls.add_argument("--api-key", default="")
    lset = sub.add_parser("leaderboard-settings", parents=[common], help="Get/set leaderboard settings")
    lset.add_argument("--api-key", default="")

    sub.add_parser("telemetry", parents=[common], help="Show system telemetry")
    sub.add_parser("build-docker", parents=[common], help="Build Docker sandbox image")
    sub.add_parser("docker-status", parents=[common], help="Check Docker status")
    sub.add_parser("version", parents=[common], help="Show CLI version")
    return p


COMMANDS = {
    "health": cmd_health, "shutdown": cmd_shutdown, "serve": cmd_serve,
    "connect": cmd_connect, "models": cmd_models, "benchmarks": cmd_benchmarks,
    "datasets": cmd_datasets, "install-dataset": cmd_install_dataset,
    "install-all": cmd_install_all, "hf-token": cmd_hf_token,
    "run": cmd_run, "batch": cmd_batch, "model-queue": cmd_model_queue,
    "model-queue-active": cmd_model_queue_active,
    "model-queue-halt": cmd_model_queue_halt, "model-queue-skip": cmd_model_queue_skip,
    "status": cmd_status, "poll": cmd_poll, "results": cmd_results,
    "history": cmd_history, "diff": cmd_diff, "comparison": cmd_comparison,
    "export": cmd_export, "export-batch": cmd_export_batch,
    "export-history": cmd_export_history, "batch-status": cmd_batch_status,
    "leaderboard": cmd_leaderboard, "leaderboard-delete": cmd_leaderboard_delete,
    "leaderboard-clear": cmd_leaderboard_clear, "leaderboard-sync": cmd_leaderboard_sync,
    "leaderboard-settings": cmd_leaderboard_settings, "telemetry": cmd_telemetry,
    "pause": cmd_pause, "resume": cmd_resume, "halt": cmd_halt,
    "build-docker": cmd_build_docker, "docker-status": cmd_docker_status, "version": cmd_version,
}


def main():
    global _json_mode, _verbose_mode

    # Pre-scan for global flags before argparse (so they work in any position)
    _json_mode = "--json" in sys.argv
    _verbose_mode = "--verbose" in sys.argv

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Also check argparse-parsed values (for when flags come after subcommand)
    if hasattr(args, "json") and args.json:
        _json_mode = True
    if hasattr(args, "verbose") and args.verbose:
        _verbose_mode = True

    if args.command == "version":
        cmd_version(args)
        sys.exit(0)

    handler = COMMANDS.get(args.command)
    if not handler:
        parser.print_help()
        sys.exit(1)

    if hasattr(args, "full") and args.full:
        args.quick_test = False

    if args.command != "serve":
        server_url = getattr(args, "server", DEFAULT_BASE)
        if not _is_server_up(server_url):
            if not _ensure_server(server_url):
                sys.exit(f"Cannot start server at {server_url}")

    try:
        handler(args)
    except httpx.ConnectError:
        sys.exit(f"Cannot connect to {args.server}. Is BenchMax running?")
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            detail = e.response.text[:200]
        endpoint = str(e.request.url) if hasattr(e, "request") else ""
        sys.exit(f"HTTP {e.response.status_code} {endpoint}: {detail}")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
