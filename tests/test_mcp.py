"""MCP surface: tool registration, /mcp route, install-mcp config merge."""
import json

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

EXPECTED_TOOLS = {
    "list_benchmarks", "run_benchmark", "run_batch", "get_status",
    "control_run", "get_results", "list_history", "compare_runs",
    "get_telemetry",
    "set_endpoint", "get_endpoint", "list_models", "check_endpoint_health",
    "register_webhook", "list_webhooks", "delete_webhook",
}


def test_all_tools_registered():
    import mcp_server
    tools = mcp_server.mcp._tool_manager._tools
    assert EXPECTED_TOOLS <= set(tools), f"missing: {EXPECTED_TOOLS - set(tools)}"


def test_mcp_route_mounted():
    from backend.main import app
    paths = [getattr(r, "path", "") for r in app.router.routes]
    assert "/mcp" in paths


def test_control_run_rejects_bad_action():
    from mcp_server import control_run
    assert control_run("1", "explode")["error"].startswith("action must be")


def test_get_mcp_info_shape():
    from backend.operations import get_mcp_info
    d = get_mcp_info()
    assert d["mounted"] is True
    assert d["endpoint"] == "/mcp"
    assert "run_benchmark" in d["tools"]
    assert d["stdio_command"][-1].endswith("mcp_server.py")
    assert "install-mcp" in d["install_command"]


async def test_mcp_info_endpoint(client):
    r = await client.get("/api/mcp/info")
    assert r.status_code == 200
    d = r.json()
    assert d["mounted"] is True and isinstance(d["tools"], list)


def test_merge_config_write_and_uninstall(tmp_path):
    from backend.ops.update import _merge_mcp_config
    cfg = tmp_path / "sub" / "mcp.json"
    _merge_mcp_config(cfg, "mcpServers", "benchmax", {"command": "py"})
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["benchmax"] == {"command": "py"}
    # Existing entries from other servers survive the merge.
    data["mcpServers"]["other"] = {"command": "x"}
    cfg.write_text(json.dumps(data))
    _merge_mcp_config(cfg, "mcpServers", "benchmax", {}, uninstall=True)
    data = json.loads(cfg.read_text())
    assert "benchmax" not in data["mcpServers"]
    assert data["mcpServers"]["other"] == {"command": "x"}


def test_merge_config_recovers_corrupt_file(tmp_path):
    from backend.ops.update import _merge_mcp_config
    cfg = tmp_path / "mcp.json"
    cfg.write_text("not json{{{")
    _merge_mcp_config(cfg, "mcpServers", "benchmax", {"command": "py"})
    assert json.loads(cfg.read_text())["mcpServers"]["benchmax"] == {"command": "py"}


def test_install_mcp_configs_end_to_end(tmp_path):
    import pytest
    from backend.ops.update import install_mcp_configs
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    srv = tmp_path / "mcp_server.py"
    srv.write_text("# stub")
    wrote = install_mcp_configs("http://127.0.0.1:8000", clients=["all"],
                                server_py=str(srv), python_exe="py",
                                home=str(home), appdata="", project_root=str(proj))
    assert set(wrote) == {"claude", "opencode", "cursor", "vscode"}
    claude = json.loads((home / "claude_desktop_config.json").read_text())
    assert claude["mcpServers"]["benchmax"]["args"] == [str(srv)]
    opin = json.loads((proj / "opencode.json").read_text())
    assert opin["mcp"]["benchmax"]["type"] == "local"
    # Uninstall removes benchmax but keeps the files.
    install_mcp_configs("http://127.0.0.1:8000", clients=["all"], uninstall=True,
                        server_py=str(srv), python_exe="py",
                        home=str(home), appdata="", project_root=str(proj))
    claude = json.loads((home / "claude_desktop_config.json").read_text())
    assert "benchmax" not in claude["mcpServers"]
    with pytest.raises(ValueError):
        install_mcp_configs("http://x", clients=["notanapp"], server_py=str(srv),
                            home=str(home), project_root=str(proj))


async def test_mcp_install_endpoint(client, monkeypatch):
    import backend.api as api_mod
    seen = {}

    def fake_install(base, clients=("all",), remote=False, uninstall=False, **kw):
        seen.update(base=base, clients=clients, remote=remote, uninstall=uninstall)
        return {"claude": "C:/fake/claude.json"}

    monkeypatch.setattr(api_mod, "install_mcp_configs", fake_install)
    r = await client.post("/api/mcp/install",
                          json={"clients": ["claude"], "url": "http://127.0.0.1:8000"})
    assert r.status_code == 200
    d = r.json()
    assert d["configs"] == {"claude": "C:/fake/claude.json"}
    assert seen == {"base": "http://127.0.0.1:8000", "clients": ["claude"],
                    "remote": False, "uninstall": False}

    def boom(*a, **kw):
        raise ValueError("Unknown MCP client(s): nope.")

    monkeypatch.setattr(api_mod, "install_mcp_configs", boom)
    r = await client.post("/api/mcp/install", json={"clients": ["nope"]})
    assert r.status_code == 400
