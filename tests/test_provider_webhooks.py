"""Provider defaults + run-completion webhooks (REST + ops)."""
import json

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def provider_file(tmp_path, monkeypatch):
    import backend.ops.datasets as ds
    f = tmp_path / ".provider.json"
    monkeypatch.setattr(ds, "PROVIDER_FILE", f)
    return f


@pytest.fixture
def webhook_file(tmp_path):
    import backend.ops.webhooks as wh
    f = tmp_path / ".webhooks.json"
    wh._reset_for_tests(f)
    yield f
    wh._reset_for_tests(None)


# ── provider URL handling ─────────────────────────────────────────────

def test_normalize_prepends_scheme():
    from backend.ops.datasets import normalize_provider_url
    assert normalize_provider_url("127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1"
    assert normalize_provider_url("http://localhost:1234/v1/") == "http://localhost:1234/v1"


def test_normalize_rejects_garbage():
    import pytest as _pt
    from backend.ops.datasets import normalize_provider_url
    with _pt.raises(ValueError):
        normalize_provider_url("ftp://x")
    with _pt.raises(ValueError):
        normalize_provider_url("http://")
    with _pt.raises(ValueError):
        normalize_provider_url("")


def test_resolve_prefers_explicit_then_default(provider_file):
    from backend.ops import datasets as ds
    assert ds.resolve_api_url("http://explicit:1/v1") == "http://explicit:1/v1"
    assert ds.resolve_api_url("") == "http://127.0.0.1:1234/v1"  # hardcoded fallback
    provider_file.write_text(json.dumps({"url": "http://saved:2/v1"}))
    assert ds.resolve_api_url("") == "http://saved:2/v1"
    assert ds.resolve_api_url("http://explicit:1/v1") == "http://explicit:1/v1"


async def test_set_and_get_default_provider(provider_file, monkeypatch):
    import backend.ops.datasets as ds

    async def fake_health(url, timeout=10.0):
        return {"url": url, "reachable": True, "latency_ms": 3,
                "models_loaded": 1, "models": ["m"]}

    monkeypatch.setattr(ds, "check_provider_health", fake_health)
    d = await ds.set_default_provider("127.0.0.1:9/v1")
    assert d["url"] == "http://127.0.0.1:9/v1" and d["reachable"] is True
    assert ds.get_default_provider() == {"url": "http://127.0.0.1:9/v1", "set": True}


async def test_health_unreachable_is_200_not_500(client):
    r = await client.get("/api/provider/health", params={"api_url": "http://127.0.0.1:9/v1"})
    assert r.status_code == 200
    d = r.json()
    assert d["reachable"] is False and d["models"] == []


async def test_models_unreachable_is_soft(client):
    r = await client.get("/api/models", params={"api_url": "http://127.0.0.1:9/v1"})
    assert r.status_code == 200
    assert r.json()["models"] == []


async def test_provider_endpoints(client, provider_file, monkeypatch):
    import backend.ops.datasets as ds

    async def fake_health(url, timeout=10.0):
        return {"url": url, "reachable": True, "latency_ms": 1,
                "models_loaded": 0, "models": []}

    monkeypatch.setattr(ds, "check_provider_health", fake_health)
    r = await client.get("/api/provider")
    assert r.status_code == 200 and r.json() == {"url": "", "set": False}
    r = await client.post("/api/provider", json={"url": "ftp://x"})
    assert r.status_code == 400
    r = await client.post("/api/provider", json={"url": "127.0.0.1:5/v1"})
    assert r.status_code == 200 and r.json()["url"] == "http://127.0.0.1:5/v1"
    r = await client.get("/api/provider")
    assert r.json() == {"url": "http://127.0.0.1:5/v1", "set": True}


# ── webhooks ──────────────────────────────────────────────────────────

def test_webhook_register_list_delete(webhook_file):
    from backend.ops import webhooks as wh
    a = wh.register_webhook("https://agent.example.com/hook")
    assert a["id"] and not a.get("duplicate")
    dup = wh.register_webhook("https://agent.example.com/hook")
    assert dup["id"] == a["id"] and dup["duplicate"] is True
    assert [h["id"] for h in wh.list_webhooks()] == [a["id"]]
    assert wh.delete_webhook("nope") is False
    assert wh.delete_webhook(a["id"]) is True
    assert wh.list_webhooks() == []


def test_webhook_rejects_bad_url(webhook_file):
    import pytest as _pt
    from backend.ops import webhooks as wh
    with _pt.raises(ValueError):
        wh.register_webhook("not-a-url")


def test_fire_never_raises_without_hooks(webhook_file):
    from backend.ops import webhooks as wh
    assert wh.fire_run_webhook(1, "COMPLETED", "m", "b", 5, 5) is None


def test_fire_posts_payload(webhook_file, monkeypatch):
    import backend.ops.webhooks as wh
    seen = []
    calls = []

    class FakeResp:
        status_code = 200

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):
            seen.append((url, json))
            return FakeResp()

    monkeypatch.setattr(wh.httpx, "Client", FakeClient)
    # Run delivery threads inline so the test is deterministic.
    monkeypatch.setattr(wh.threading, "Thread",
                        lambda target, args, daemon: calls.append((target, args)) or _Joiner(target, args))
    wh.register_webhook("https://agent.example.com/hook")
    wh.fire_run_webhook(7, "FAILED", "m", "HumanEval", 3, 5)
    assert len(calls) == 1
    assert seen[0][1]["event"] == "run.completed" and seen[0][1]["run_id"] == 7


class _Joiner:
    def __init__(self, target, args):
        target(*args)

    def start(self):
        pass


async def test_webhook_endpoints(client, webhook_file):
    r = await client.post("/api/webhooks", json={"url": "bogus"})
    assert r.status_code == 400
    r = await client.post("/api/webhooks", json={"url": "https://agent.example.com/hook"})
    assert r.status_code == 201
    hook_id = r.json()["id"]
    r = await client.get("/api/webhooks")
    assert [h["id"] for h in r.json()["webhooks"]] == [hook_id]
    r = await client.delete("/api/webhooks/nope")
    assert r.status_code == 404
    r = await client.delete(f"/api/webhooks/{hook_id}")
    assert r.json() == {"status": "deleted"}
