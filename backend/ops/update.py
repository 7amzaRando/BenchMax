"""GitHub-release update checker — notify + download link, never auto-install.

Design notes:
- One public function: ``get_version_info(refresh=False)``. Always returns
  a dict, never raises — offline / rate-limited / malformed responses yield
  ``latest: None`` so the endpoint stays HTTP 200 and the UI fails silent.
- 24h TTL cache in module globals (thread-safe via lock). ``refresh=True``
  bypasses the cache for the manual "Check now" button.
- Same message for frozen .exe and source installs (per user decision):
  a Download button pointing at the release asset plus a Release-notes link.
  No self-replacement logic — a running .exe can't replace itself on Windows.
"""
import logging
import re
import threading
import time

logger = logging.getLogger(__name__)

GITHUB_OWNER = "7amzaRando"
GITHUB_REPO = "BenchMax"
GITHUB_LATEST_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
# Direct download that always resolves to the newest attached .exe.
LATEST_DOWNLOAD_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest/download/BenchMax.exe"

CACHE_TTL_SECS = 24 * 3600

_cache: dict = {"at": 0.0, "payload": None}
_cache_lock = threading.Lock()


def _parse_version(tag: str) -> tuple[int, ...]:
    """Parse 'v2.0.3' / '2.0.3' into a comparable tuple. Unparseable -> ()."""
    m = re.search(r"(\d+(?:\.\d+)*)", tag or "")
    if not m:
        return ()
    try:
        return tuple(int(p) for p in m.group(1).split("."))
    except ValueError:
        return ()


def _pad(a: tuple[int, ...], n: int) -> tuple[int, ...]:
    return a + (0,) * (n - len(a))


def is_newer(current: str, latest: str) -> bool:
    """True when latest parses and compares greater than current."""
    c, l = _parse_version(current), _parse_version(latest)
    if not l or not c:
        return False
    n = max(len(c), len(l))
    return _pad(l, n) > _pad(c, n)


def _fetch_latest_release() -> dict | None:
    """Hit the GitHub releases API. Returns the JSON dict or None on any failure."""
    try:
        import httpx

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                GITHUB_LATEST_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "BenchMax",
                },
            )
        if resp.status_code != 200:
            logger.info("Update check: GitHub API status %s", resp.status_code)
            return None
        data = resp.json()
        if not isinstance(data, dict) or not data.get("tag_name"):
            return None
        return data
    except Exception as e:
        logger.info("Update check failed (offline?): %s", e)
        return None


def get_version_info(refresh: bool = False) -> dict:
    """Return version + update status. Never raises.

    Shape: {current, latest, update_available, html_url, published_at,
    name, notes_excerpt, download_url, asset_name, asset_size, checked_at}
    """
    from backend.version import __version__

    now = time.time()
    with _cache_lock:
        cached = _cache["payload"] if not refresh else None
        if cached is not None and (now - _cache["at"]) < CACHE_TTL_SECS:
            payload = dict(cached)
            payload["current"] = __version__
            payload["update_available"] = is_newer(__version__, payload.get("latest") or "")
            return payload

    data = _fetch_latest_release()
    if data is None:
        return {
            "current": __version__,
            "latest": None,
            "update_available": False,
            "html_url": None,
            "published_at": None,
            "name": None,
            "notes_excerpt": None,
            "download_url": LATEST_DOWNLOAD_URL,
            "asset_name": None,
            "asset_size": None,
            "checked_at": int(now),
        }

    tag = str(data.get("tag_name") or "")
    assets = data.get("assets") or []
    exe_asset = None
    for a in assets:
        if isinstance(a, dict) and str(a.get("name", "")).lower().endswith(".exe"):
            exe_asset = a
            break
    body = str(data.get("body") or "")
    excerpt = body[:500] + ("…" if len(body) > 500 else "") if body else None
    payload = {
        "current": __version__,
        "latest": tag.lstrip("v") if tag.startswith("v") else tag,
        "latest_tag": tag,
        "update_available": is_newer(__version__, tag),
        "html_url": data.get("html_url"),
        "published_at": data.get("published_at"),
        "name": data.get("name"),
        "notes_excerpt": excerpt,
        "download_url": (
            exe_asset.get("browser_download_url")
            if isinstance(exe_asset, dict)
            else LATEST_DOWNLOAD_URL
        ),
        "asset_name": exe_asset.get("name") if isinstance(exe_asset, dict) else None,
        "asset_size": exe_asset.get("size") if isinstance(exe_asset, dict) else None,
        "checked_at": int(now),
    }
    with _cache_lock:
        _cache["at"] = now
        _cache["payload"] = dict(payload)
    return payload


def clear_version_cache() -> None:
    """Test helper: reset the TTL cache."""
    with _cache_lock:
        _cache["at"] = 0.0
        _cache["payload"] = None


MCP_CLIENTS = ("claude", "opencode", "cursor", "vscode")


def _mcp_client_specs(appdata, home, project_root):
    """Config file + container key per app. Test paths are injectable."""
    from pathlib import Path
    return {
        # Claude Desktop / Cursor share the mcpServers stdio shape.
        "claude": (Path(appdata) / "Claude" / "claude_desktop_config.json"
                   if appdata else Path(home) / "claude_desktop_config.json",
                   "mcpServers"),
        "opencode": (Path(project_root) / "opencode.json", "mcp"),
        "cursor": (Path(home) / ".cursor" / "mcp.json", "mcpServers"),
        "vscode": (Path(project_root) / ".vscode" / "mcp.json", "servers"),
    }


def mcp_config_entry(client, python_exe, server_py, base, remote=False):
    """One benchmax entry in the client's native format (mirrored by the
    Settings tab snippet preview — keep both in sync)."""
    env = {"BENCHMAX_URL": base}
    if remote:
        if client == "opencode":
            return {"type": "remote", "url": base + "/mcp", "enabled": True}
        if client == "vscode":
            return {"type": "http", "url": base + "/mcp"}
        if client == "cursor":
            return {"url": base + "/mcp"}
        # Claude Desktop has no reliable remote support — keep stdio.
    if client == "opencode":
        return {"type": "local", "command": [python_exe, server_py],
                "environment": env, "enabled": True}
    if client == "vscode":
        return {"type": "stdio", "command": python_exe,
                "args": [server_py], "env": env}
    return {"command": python_exe, "args": [server_py], "env": env}


def _merge_mcp_config(path, container, name, entry, uninstall=False):
    """Merge one server entry into a JSON config file without touching
    other servers. Corrupt/missing files start fresh. Returns str(path)."""
    import json
    from pathlib import Path
    path = Path(path)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    servers = data.get(container)
    if not isinstance(servers, dict):
        servers = {}
    if uninstall:
        servers.pop(name, None)
    else:
        servers[name] = entry
    data[container] = servers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return str(path)


def install_mcp_configs(base, clients=("all",), remote=False, uninstall=False,
                        python_exe=None, server_py=None,
                        home=None, appdata=None, project_root=None):
    """Write (or remove) the benchmax entry in MCP client configs.

    Paths default to the real user/project locations; tests inject tmp
    dirs. Unknown client names raise ValueError. Returns {client: path}.
    """
    import os
    import sys
    from pathlib import Path
    if isinstance(clients, str):
        clients = [clients]
    clients = [c.lower() for c in clients]
    if clients == ["all"]:
        clients = list(MCP_CLIENTS)
    unknown = [c for c in clients if c not in MCP_CLIENTS]
    if unknown:
        raise ValueError(f"Unknown MCP client(s): {', '.join(unknown)}. Use all|{'|'.join(MCP_CLIENTS)}.")
    root = Path(__file__).resolve().parents[2]
    server_py = server_py or str(root / "mcp_server.py")
    if not Path(server_py).exists():
        raise FileNotFoundError("mcp_server.py not found next to the BenchMax root.")
    python_exe = python_exe or str(Path(sys.executable).resolve())
    home = home or str(Path.home())
    appdata = appdata if appdata is not None else os.environ.get("APPDATA", "")
    project_root = project_root or str(root)
    specs = _mcp_client_specs(appdata, home, project_root)
    base = (base or "http://127.0.0.1:8000").rstrip("/")
    wrote = {}
    for client in clients:
        path, container = specs[client]
        entry = mcp_config_entry(client, python_exe, server_py, base, remote)
        wrote[client] = _merge_mcp_config(path, container, "benchmax", entry, uninstall)
    return wrote


def get_mcp_info() -> dict:
    """MCP access info for clients (Settings tab, installers).

    Always returns a dict, never raises — if the mcp package is missing
    the endpoint still answers with mounted=False so the UI degrades
    to showing the manual install command.
    """
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    try:
        from mcp_server import mcp as _mcp
        tools = sorted(_mcp._tool_manager._tools)
        mounted = True
    except Exception:
        tools, mounted = [], False
    return {
        "mounted": mounted,
        "endpoint": "/mcp",
        "tools": tools,
        "stdio_command": [sys.executable, str(root / "mcp_server.py")],
        "install_command": "py cli.py install-mcp --client all",
    }
