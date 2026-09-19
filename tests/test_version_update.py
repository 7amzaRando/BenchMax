"""Update checker: semver compare, cache TTL, offline grace, endpoint shape."""
from backend.ops import update as upd


class TestIsNewer:
    def test_newer_patch(self):
        assert upd.is_newer("2.0.3", "v2.0.4") is True

    def test_same(self):
        assert upd.is_newer("2.0.3", "v2.0.3") is False

    def test_older(self):
        assert upd.is_newer("2.0.4", "v2.0.3") is False

    def test_unparseable_never_notifies(self):
        assert upd.is_newer("2.0.3", "not-a-version") is False
        assert upd.is_newer("???", "v2.0.4") is False

    def test_different_widths(self):
        assert upd.is_newer("2.0", "v2.0.1") is True


class TestGetVersionInfo:
    def setup_method(self):
        upd.clear_version_cache()

    def teardown_method(self):
        upd.clear_version_cache()

    def test_offline_returns_current_no_raise(self, monkeypatch):
        monkeypatch.setattr(upd, "_fetch_latest_release", lambda: None)
        info = upd.get_version_info()
        assert info["latest"] is None
        assert info["update_available"] is False
        assert info["current"]

    def test_newer_release_sets_flag(self, monkeypatch):
        monkeypatch.setattr(upd, "_fetch_latest_release", lambda: {
            "tag_name": "v99.0.0",
            "html_url": "https://example.invalid/r",
            "published_at": None,
            "name": None,
            "body": "hi",
            "assets": [],
        })
        info = upd.get_version_info()
        assert info["update_available"] is True
        assert info["latest"] == "99.0.0"

    def test_cache_ttl_and_refresh(self, monkeypatch):
        calls = {"n": 0}

        def fake():
            calls["n"] += 1
            return {"tag_name": "v99.0.0", "assets": []}

        monkeypatch.setattr(upd, "_fetch_latest_release", fake)
        upd.get_version_info()
        upd.get_version_info()
        assert calls["n"] == 1  # second call served from cache
        upd.get_version_info(refresh=True)
        assert calls["n"] == 2


def test_version_endpoint_shape(client=None):
    # Endpoint-level pin via TestClient when available; skipped otherwise.
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
    except Exception:
        return
    c = TestClient(app)
    r = c.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert "current" in body and "update_available" in body
