"""LAN password gate: loopback stays open, LAN needs a Bearer token."""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend import auth as lan_auth


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def clean_password_file():
    lan_auth.PASSWORD_FILE.unlink(missing_ok=True)
    lan_auth._active_tokens.clear()
    yield
    lan_auth.PASSWORD_FILE.unlink(missing_ok=True)
    lan_auth._active_tokens.clear()


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeReq:
    def __init__(self, host, token=None):
        self.client = _FakeClient(host)
        self.headers = {"authorization": f"Bearer {token}"} if token else {}


@pytest.mark.asyncio
async def test_auth_status_open_on_loopback(client, clean_password_file):
    resp = await client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lan_required"] is False
    assert data["password_set"] is False
    assert data["authenticated"] is True


@pytest.mark.asyncio
async def test_setup_rejects_empty(client, clean_password_file):
    resp = await client.post("/api/auth/setup", json={"password": "  "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_setup_login_roundtrip(client, clean_password_file):
    assert (await client.post("/api/auth/setup", json={"password": "owner-secret"})).status_code == 200
    assert lan_auth.password_is_set()
    # Wrong password rejected
    assert (await client.post("/api/auth/login", json={"password": "nope"})).status_code == 401
    # Right password issues a token
    resp = await client.post("/api/auth/login", json={"password": "owner-secret"})
    assert resp.status_code == 200
    assert len(resp.json()["token"]) == 64


@pytest.mark.asyncio
async def test_login_without_password_is_conflict(client, clean_password_file):
    resp = await client.post("/api/auth/login", json={"password": "anything"})
    assert resp.status_code == 409


def test_lan_gate_matrix(clean_password_file):
    # No password set: loopback open, LAN closed
    assert lan_auth.lan_request_allowed(_FakeReq("127.0.0.1")) is True
    assert lan_auth.lan_request_allowed(_FakeReq("::1")) is True
    assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5")) is False
    # With password + token: LAN open with token, closed without
    lan_auth.set_password("owner-secret")
    token, _ = lan_auth.issue_token()
    assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5", token)) is True
    assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5", "bogus")) is False
    assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5")) is False
    # Rotating the password kills existing sessions
    lan_auth.set_password("brand-new")
    assert lan_auth.lan_request_allowed(_FakeReq("192.168.1.5", token)) is False
    assert lan_auth.verify_password("brand-new") is True
    assert lan_auth.verify_password("owner-secret") is False
