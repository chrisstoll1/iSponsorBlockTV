import pytest
from fastapi.testclient import TestClient

from dashboard.backend.main import create_app
from iSponsorBlockTV.api_helpers import ApiHelper


@pytest.fixture
def dashboard(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>dashboard</html>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("private", encoding="utf-8")
    app = create_app(tmp_path / "data" / "config.json", static, password="test-secret")
    with TestClient(app) as client:
        yield client, tmp_path


def test_authentication_and_health(dashboard):
    client, _ = dashboard
    assert client.get("/health").json() == {"status": "ok"}
    for path in ("/", "/api/config", "/assets/app.js"):
        response = client.get(path)
        assert response.status_code == 401
        assert "Basic" in response.headers["www-authenticate"]
    assert client.get("/api/config", auth=("admin", "wrong")).status_code == 401
    assert (
        client.get("/api/config", headers={"Authorization": "Basic invalid!!"}).status_code == 401
    )
    assert client.get("/api/config", auth=("admin", "test-secret")).status_code == 200


def test_save_validates_creates_directory_and_preserves_previous_config(dashboard):
    client, root = dashboard
    client.auth = ("admin", "test-secret")
    response = client.post("/api/config", json={"join_name": "Living room"})
    assert response.status_code == 200
    assert response.json()["config"]["join_name"] == "Living room"
    before = (root / "data" / "config.json").read_bytes()
    assert client.post("/api/config", json={"devices": "broken"}).status_code == 422
    assert (root / "data" / "config.json").read_bytes() == before
    assert client.get("/api/config").headers["cache-control"] == "no-store"


def test_invalid_stored_config_does_not_leak_contents(dashboard):
    client, root = dashboard
    client.auth = ("admin", "test-secret")
    (root / "data").mkdir()
    (root / "data" / "config.json").write_text('{"apikey": "private",', encoding="utf-8")
    response = client.get("/api/config")
    assert response.status_code == 409
    assert "private" not in response.text


def test_cross_origin_writes_are_rejected(dashboard):
    client, _ = dashboard
    client.auth = ("admin", "test-secret")
    assert (
        client.post("/api/config", json={}, headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    assert (
        client.post("/api/config", json={}, headers={"Origin": "http://testserver"}).status_code
        == 200
    )


def test_static_traversal_and_unknown_api_routes_are_rejected(dashboard):
    client, _ = dashboard
    client.auth = ("admin", "test-secret")
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    for path in ("/%2e%2e/secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt", "/api/missing"):
        assert client.get(path).status_code == 404
    assert "private" not in client.get("/%2e%2e/secret.txt").text


def test_pairing_uses_current_upstream_helper_and_preserves_leading_zero(dashboard, monkeypatch):
    client, _ = dashboard
    client.auth = ("admin", "test-secret")
    calls = []

    async def pair(self, code):
        calls.append(code)
        return {"screen_id": "current-screen-id", "name": "TV", "lounge_token": "not-returned"}

    monkeypatch.setattr(ApiHelper, "pair_with_code", pair)
    response = client.post("/api/pair", json={"code": "012-345-678-901", "offset": -200})
    assert response.status_code == 200
    assert calls == ["012345678901"]
    assert response.json() == {"screen_id": "current-screen-id", "name": "TV", "offset": -200}
    assert client.post("/api/pair", json={"code": "invalid"}).status_code == 422


def test_search_uses_complete_current_configuration(dashboard, monkeypatch):
    client, _ = dashboard
    client.auth = ("admin", "test-secret")
    assert client.get("/api/channels/search?query=test").status_code == 400
    client.post("/api/config", json={"apikey": "test-key"})
    calls = []

    async def search(self, query):
        calls.append((self.apikey, self.sponsorblock_api_url, query))
        return [("UC123", "Channel", "1,000")]

    monkeypatch.setattr(ApiHelper, "search_channels", search)
    response = client.get("/api/channels/search?query=test")
    assert response.json() == [{"id": "UC123", "name": "Channel", "subscribers": "1,000"}]
    assert calls[0][0] == "test-key"


def test_authentication_is_required_at_startup(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD_FILE", raising=False)
    with (
        pytest.raises(RuntimeError, match="Set DASHBOARD_PASSWORD"),
        TestClient(create_app(tmp_path / "config.json", tmp_path)),
    ):
        pass


def test_password_file(dashboard, tmp_path):
    password_file = tmp_path / "password"
    password_file.write_text("file-secret\n", encoding="utf-8")
    with TestClient(
        create_app(tmp_path / "config.json", tmp_path, password_file=password_file)
    ) as client:
        assert client.get("/api/config", auth=("admin", "file-secret")).status_code == 200
