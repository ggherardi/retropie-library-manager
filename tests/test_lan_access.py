import json
import secrets

import pytest
from fastapi.testclient import TestClient

from backend.lan_access import COOKIE, IDLE_SECONDS, Access, atomic_json
from backend.main import create_app

INTERFACE = {
    "address": "192.168.44.20",
    "prefix": 24,
    "subnet": "192.168.44.0/24",
    "name": "Synthetic Ethernet",
    "private": True,
}
HEADERS = {"X-RLM-Request": "1"}


@pytest.fixture
def secured(tmp_path, monkeypatch):
    monkeypatch.setattr(Access, "interfaces", lambda self: [dict(INTERFACE)])
    app = create_app(tmp_path / "data")
    password = secrets.token_urlsafe(20)
    with TestClient(app, headers=HEADERS, client=("127.0.0.1", 1234)) as client:
        status = client.get("/api/access/status").json()
        response = client.post(
            "/api/access/setup", json={"password": password, "setup_token": status["setup_token"]}
        )
        assert response.status_code == 200, response.text
        client.headers["X-RLM-CSRF"] = response.json()["csrf"]
        yield app, client, password


def enable(app):
    app.state.access.lan_active = True
    atomic_json(app.state.access.network_file, {"lan_enabled": True, "port": 8000})


def test_setup_hash_and_session_cookie(secured):
    app, client, password = secured
    raw = app.state.access.admin_file.read_text()
    assert password not in raw and json.loads(raw)["algorithm"] == "scrypt"
    assert client.cookies.get(COOKIE)
    assert client.get("/api/settings").status_code == 200
    assert (
        client.post("/api/access/setup", json={"password": password, "setup_token": "invalid"}).status_code
        == 403
    )
    with app.state.access.connection() as db:
        stored = db.execute("select token from sessions").fetchone()[0]
    assert stored != client.cookies.get(COOKIE)


@pytest.mark.parametrize(
    "path",
    [
        "/api/games",
        "/api/settings",
        "/api/devices",
        "/api/installations",
        "/api/access/network",
        "/api/access/qr",
        "/docs",
        "/openapi.json",
    ],
)
def test_api_and_diagnostics_are_protected(secured, path):
    _, client, _ = secured
    client.cookies.clear()
    assert client.get(path).status_code == 401


def test_csrf_and_origin_are_enforced(secured):
    _, client, _ = secured
    body = {"import_roots": [], "export_root": ""}
    assert client.put("/api/settings", json=body, headers={"X-RLM-CSRF": "wrong"}).status_code == 403
    assert (
        client.put("/api/settings", json=body, headers={"Origin": "http://evil.invalid"}).status_code == 403
    )
    assert client.put("/api/settings", json=body).status_code == 200


def test_lan_requires_private_subnet_authentication_and_ignores_forwarded_headers(secured):
    app, _, password = secured
    enable(app)
    with TestClient(
        app, base_url="http://192.168.44.20:8000", headers=HEADERS, client=("192.168.44.12", 5000)
    ) as remote:
        assert remote.get("/").status_code == 200
        assert remote.get("/api/games").status_code == 401
        response = remote.post("/api/access/login", json={"password": password})
        assert response.status_code == 200
        remote.headers["X-RLM-CSRF"] = response.json()["csrf"]
        assert remote.get("/api/games").status_code == 200
        assert remote.put("/api/access/network", json={"lan_enabled": True, "port": 8000}).status_code == 403
        assert remote.post("/api/access/logout").status_code == 200
        assert remote.get("/api/games").status_code == 401
    with TestClient(
        app,
        base_url="http://192.168.44.20:8000",
        headers={"X-Forwarded-For": "127.0.0.1"},
        client=("203.0.113.8", 5000),
    ) as outsider:
        assert outsider.get("/api/health").status_code == 403


def test_lan_closed_without_admin_or_private_network(tmp_path, monkeypatch):
    monkeypatch.setattr(Access, "interfaces", lambda self: [dict(INTERFACE, private=False)])
    app = create_app(tmp_path / "data")
    app.state.access.lan_active = True
    atomic_json(app.state.access.network_file, {"lan_enabled": True, "port": 8000})
    with TestClient(
        app, base_url="http://192.168.44.20:8000", client=("192.168.44.10", 5000), headers=HEADERS
    ) as remote:
        assert remote.get("/").status_code == 403
        assert (
            remote.post("/api/access/setup", json={"password": secrets.token_urlsafe(20)}).status_code == 403
        )


def test_login_rate_limit_persists_and_does_not_echo_password(secured):
    app, client, _ = secured
    client.cookies.clear()
    secret = secrets.token_urlsafe(20)
    for _ in range(5):
        response = client.post("/api/access/login", json={"password": secret})
        assert response.status_code == 401 and secret not in response.text
    # Fresh service instance uses the same persistent rate limiter.
    other = Access(app.state.access.data)
    with pytest.raises(Exception) as error:
        other.throttle("127.0.0.1")
    assert error.value.status_code == 429
    assert client.post("/api/access/login", json={"password": secret}).status_code == 429


def test_logout_revokes_token_and_idle_expiry(secured, monkeypatch):
    app, client, _ = secured
    stolen = client.cookies.get(COOKIE)
    assert client.post("/api/access/logout").status_code == 200
    client.cookies.set(COOKIE, stolen)
    assert client.get("/api/games").status_code == 401


def test_idle_session_expires(secured, monkeypatch):
    import time

    _, client, _ = secured
    stamp = time.time()
    monkeypatch.setattr("backend.lan_access.time.time", lambda: stamp + IDLE_SECONDS + 1)
    assert client.get("/api/games").status_code == 401


def test_network_persistence_and_qr_contains_only_real_address(secured):
    app, client, _ = secured
    response = client.put("/api/access/network", json={"lan_enabled": True, "port": 8000})
    assert response.status_code == 200 and response.json()["restart_needed"]
    assert Access(app.state.access.data).config() == {"lan_enabled": True, "port": 8000}
    app.state.access.lan_active = True
    response = client.get("/api/access/network")
    assert response.json()["lan_urls"] == ["http://192.168.44.20:8000"]
    assert client.get("/api/access/qr").content.startswith(b"\x89PNG")


def test_no_wildcard_cors_or_untrusted_host(secured):
    _, client, _ = secured
    assert client.get("/api/games", headers={"Host": "attacker.invalid"}).status_code == 400
    response = client.options(
        "/api/settings", headers={"Origin": "http://evil.invalid", "Access-Control-Request-Method": "PUT"}
    )
    assert response.headers.get("Access-Control-Allow-Origin") != "*"


def test_credential_validation_does_not_echo_input(secured):
    _, client, password = secured
    response = client.post("/api/access/login", json={"password": {"raw": password}})
    assert response.status_code == 422 and password not in response.text


def test_scrypt_concurrency_has_a_memory_bound(secured):
    app, client, password = secured
    slots = app.state.access.password_slots
    assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
    try:
        response = client.post("/api/access/login", json={"password": password})
        assert response.status_code == 429 and response.headers["Retry-After"] == "5"
    finally:
        slots.release()
        slots.release()
    assert client.post("/api/access/login", json={"password": password}).status_code == 200


def test_cookie_flags_https_and_token_rotation(secured):
    app, client, password = secured
    old = client.cookies.get(COOKIE)
    response = client.post("/api/access/login", json={"password": password})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "secure" not in cookie
    assert old != client.cookies.get(COOKIE)
    with app.state.access.connection() as db:
        import hashlib

        assert not db.execute(
            "select 1 from sessions where token=?", (hashlib.sha256(old.encode()).hexdigest(),)
        ).fetchone()
    with TestClient(
        app, base_url="https://127.0.0.1:8000", headers=HEADERS, client=("127.0.0.1", 5000)
    ) as tls:
        response = tls.post("/api/access/login", json={"password": password})
        assert response.status_code == 200 and "secure" in response.headers["set-cookie"].lower()
        assert tls.get("/api/games").status_code == 200
        info = tls.get("/api/access/network").json()
        assert info["local_url"] == "https://127.0.0.1:8000"


def test_absolute_session_expiry_even_when_recently_used(secured):
    import time

    from backend.lan_access import ABSOLUTE_SECONDS

    app, client, _ = secured
    with app.state.access.connection() as db:
        db.execute("update sessions set created=?, seen=?", (time.time() - ABSOLUTE_SECONDS - 1, time.time()))
    assert client.get("/api/games").status_code == 401


def test_initial_setup_nonce_and_password_bounds(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, headers=HEADERS, client=("127.0.0.1", 5000)) as client:
        token = client.get("/api/access/status").json()["setup_token"]
        assert (
            client.post("/api/access/setup", json={"password": secrets.token_urlsafe(20)}).status_code == 403
        )
        assert (
            client.post("/api/access/setup", json={"password": "short", "setup_token": token}).status_code
            == 400
        )
        assert not app.state.access.configured()


def test_public_network_and_invalid_port_cannot_be_enabled(secured, monkeypatch):
    app, client, _ = secured
    monkeypatch.setattr(Access, "interfaces", lambda self: [dict(INTERFACE, private=False)])
    assert client.put("/api/access/network", json={"lan_enabled": True, "port": 8000}).status_code == 400
    assert client.put("/api/access/network", json={"lan_enabled": False, "port": 80}).status_code == 400
    assert not app.state.access.network_file.exists()
