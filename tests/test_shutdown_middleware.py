"""Shutdown endpoint + LAN middleware + /api/v1 mirror parity.

Pins actual production behavior (no prod changes):
- POST /api/shutdown with a wrong token -> 401; empty token from
  loopback (test client) is accepted -> 200; ?token= query back-compat works.
- The shutdown kill thread is stubbed so tests never call os._exit.
- LAN middleware: gated routes 401 when the gate denies; /api/health and
  /api/auth/* stay open.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class _NoopThread:
    """Stands in for threading.Thread so the shutdown killer never runs."""

    instances = []

    def __init__(self, *args, **kwargs):
        _NoopThread.instances.append((args, kwargs))

    def start(self):
        pass


@pytest.fixture
def no_shutdown():
    _NoopThread.instances.clear()
    with patch("backend.main.threading.Thread", _NoopThread):
        yield _NoopThread
    _NoopThread.instances.clear()


class TestShutdownEndpoint:
    @pytest.mark.asyncio
    async def test_wrong_token_rejected(self, client):
        resp = await client.post("/api/shutdown", json={"token": "wrong-token"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_token_loopback_accepted(self, client, no_shutdown):
        # Empty token from localhost is accepted (actual behavior — the
        # localhost caller is already trusted); shutdown is scheduled.
        resp = await client.post("/api/shutdown", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "shutting_down"
        assert len(_NoopThread.instances) == 1

    @pytest.mark.asyncio
    async def test_correct_token_accepted(self, client, no_shutdown):
        with patch("backend.main._admin_token", "secret123"):
            resp = await client.post("/api/shutdown", json={"token": "secret123"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "shutting_down"
        assert len(_NoopThread.instances) == 1

    @pytest.mark.asyncio
    async def test_query_param_backcompat(self, client, no_shutdown):
        with patch("backend.main._admin_token", "secret123"):
            ok = await client.post("/api/shutdown?token=secret123", json={})
            bad = await client.post("/api/shutdown?token=nope", json={})
        assert ok.status_code == 200
        assert bad.status_code == 401


class TestLanMiddleware:
    @pytest.mark.asyncio
    async def test_gated_route_denied_when_gate_closed(self, client):
        with patch("backend.auth.lan_request_allowed", return_value=False):
            resp = await client.get("/api/benchmarks")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_health_open_without_auth(self, client):
        # Health stays open even when the LAN gate denies everything else.
        with patch("backend.auth.lan_request_allowed", return_value=False):
            resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_auth_status_open_without_auth(self, client):
        with patch("backend.auth.lan_request_allowed", return_value=False):
            resp = await client.get("/api/auth/status")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_loopback_allowed_on_gated_route(self, client):
        resp = await client.get("/api/benchmarks")
        assert resp.status_code == 200

    def test_lan_gate_matrix(self):
        from backend import auth as lan_auth

        lan_auth._active_tokens.clear()

        class _FakeClient:
            def __init__(self, host):
                self.host = host

        class _FakeReq:
            def __init__(self, host, token=None):
                self.client = _FakeClient(host)
                self.headers = {"authorization": f"Bearer {token}"} if token else {}

        assert lan_auth.lan_request_allowed(_FakeReq("127.0.0.1")) is True
        assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5")) is False
        token, _ = lan_auth.issue_token()
        assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5", token)) is True
        assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5", "bogus")) is False
        lan_auth._active_tokens.clear()


class TestV1MirrorParity:
    @pytest.mark.asyncio
    async def test_benchmarks_mirror_matches(self, client):
        plain = await client.get("/api/benchmarks")
        mirrored = await client.get("/api/v1/benchmarks")
        assert plain.status_code == mirrored.status_code == 200
        assert mirrored.json() == plain.json()
