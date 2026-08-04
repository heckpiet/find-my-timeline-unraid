from find_my_timeline.database import LocationDatabase
from find_my_timeline.identity import AppleIdentityStore
from find_my_timeline.web import create_app
from find_my_timeline.web_admin import WebAdminStore


class PollerStub:
    def __init__(self):
        self.wake_calls = 0

    def status(self):
        return {
            "state": "running",
            "last_attempt_at": None,
            "last_success_at": "2026-08-03T12:00:00+00:00",
            "next_poll_at": None,
            "last_error": None,
        }

    def wake(self):
        self.wake_calls += 1

    def set_auth(self, auth):
        self.auth = auth
        self.wake()


class AuthStub:
    username = "person@example.com"
    password = None

    def __init__(self, username="person@example.com", password=None):
        self.username = username
        self.password = password

    def authentication_metadata(self, lifetime_days):
        return {"configured": True, "state": "valid", "remaining_days": lifetime_days}

    def begin_web_authentication(self, password):
        return {"requires_2fa": True, "status": "waiting_for_code"}

    def complete_web_2fa(self, code):
        return None

    def get_devices(self):
        return []


def make_client(tmp_path, monkeypatch, with_auth=False):
    monkeypatch.delenv("WEB_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("WEB_ADMIN_PASSWORD", "test-admin-password" if with_auth else "")
    monkeypatch.setenv("POLL_MIN_INTERVAL", "7")
    monkeypatch.setenv("POLL_MAX_INTERVAL", "10")
    monkeypatch.setenv("AUTH_RETRY_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("TZ", "Europe/Berlin")
    database = LocationDatabase(tmp_path / "locations.db")
    poller = PollerStub()
    app = create_app(
        database,
        AuthStub() if with_auth else None,
        poller,
        WebAdminStore(tmp_path / "session"),
        AppleIdentityStore(tmp_path / "session"),
    )
    app.config.update(TESTING=True)
    return app.test_client(), poller


def test_health_and_system_status(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)

    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    response = client.get("/api/system/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["poller"]["state"] == "running"
    assert payload["version"]
    assert payload["configuration"] == {
        "poll_min_interval": 7,
        "poll_max_interval": 10,
        "auth_retry_interval": 5,
        "timezone": "Europe/Berlin",
        "web_auth_enabled": True,
    }

    index = client.get("/")
    assert index.status_code == 200
    assert b"Settings &amp; status" in index.data
    assert f"v{payload['version']}".encode() in index.data
    assert f"/static/app.js?v={payload['version']}".encode() in index.data
    assert f"/static/auth.js?v={payload['version']}".encode() in index.data
    assert "frame-ancestors 'none'" in index.headers["Content-Security-Policy"]
    assert index.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert index.headers["Cache-Control"] == "no-store"

    static_asset = client.get("/static/app.js")
    assert static_asset.status_code == 200
    assert static_asset.headers["Cache-Control"].startswith("public, max-age=3600")

    auth_asset = client.get("/static/auth.js")
    assert auth_asset.status_code == 200
    assert b"Apple ID email address" in auth_asset.data
    assert b"Password for this Apple ID" in auth_asset.data
    assert auth_asset.data.count(b'data-password-target="') == 3
    assert b"Apple ID used for Find My" in auth_asset.data
    assert b"Security and storage details" in auth_asset.data


def test_location_query_rejects_invalid_parameters(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)

    assert client.get("/api/locations?limit=0").status_code == 400
    assert client.get("/api/locations?limit=5001").status_code == 400
    assert client.get("/api/locations?start=not-a-date").status_code == 400
    assert client.get("/api/locations?hours=-1").status_code == 400


def test_successful_web_reauthentication_wakes_poller(tmp_path, monkeypatch):
    client, poller = make_client(tmp_path, monkeypatch, with_auth=True)
    headers = {"X-Admin-Password": "test-admin-password"}

    started = client.post("/api/auth/start", headers=headers, json={"password": "not-stored"})
    assert started.status_code == 200
    verified = client.post("/api/auth/verify", headers=headers, json={"code": "123456"})

    assert verified.status_code == 200
    assert poller.wake_calls == 1


def test_first_run_setup_ignores_legacy_disabled_flag_and_persists_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_ENABLED", "false")
    monkeypatch.delenv("WEB_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("WEB_ADMIN_PASSWORD", raising=False)
    database = LocationDatabase(tmp_path / "locations.db")
    poller = PollerStub()
    store = WebAdminStore(tmp_path / "session")
    app = create_app(
        database,
        AuthStub(),
        poller,
        store,
        AppleIdentityStore(tmp_path / "session"),
    )
    app.config.update(TESTING=True)
    client = app.test_client()

    status = client.get("/api/auth/status").get_json()
    assert status["web_auth_enabled"] is True
    assert status["setup_required"] is True

    password = "new-admin-password"
    started = client.post(
        "/api/auth/start",
        json={"password": "apple-password", "admin_password": password},
    )
    assert started.status_code == 200
    verified = client.post(
        "/api/auth/verify",
        headers={"X-Admin-Password": password},
        json={"code": "123456"},
    )

    assert verified.status_code == 200
    assert store.configured
    assert store.verify(password)
    assert password not in store.path.read_text(encoding="utf-8")
    assert poller.wake_calls == 1


def test_new_explicit_disable_flag_blocks_web_authentication(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_DISABLED", "true")
    monkeypatch.delenv("WEB_ADMIN_PASSWORD", raising=False)
    database = LocationDatabase(tmp_path / "locations.db")
    app = create_app(
        database,
        AuthStub(),
        PollerStub(),
        WebAdminStore(tmp_path / "session"),
        AppleIdentityStore(tmp_path / "session"),
    )
    app.config.update(TESTING=True)
    client = app.test_client()

    status = client.get("/api/auth/status").get_json()
    assert status["web_auth_enabled"] is False
    response = client.post(
        "/api/auth/start",
        json={"password": "apple-password", "admin_password": "new-admin-password"},
    )
    assert response.status_code == 404


def test_first_run_accepts_and_persists_apple_id_from_webui(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr("find_my_timeline.web.ICloudAuth", AuthStub)
    database = LocationDatabase(tmp_path / "locations.db")
    session_directory = tmp_path / "session"
    identity_store = AppleIdentityStore(session_directory)
    poller = PollerStub()
    app = create_app(
        database,
        None,
        poller,
        WebAdminStore(session_directory),
        identity_store,
    )
    app.config.update(TESTING=True)
    client = app.test_client()

    status = client.get("/api/auth/status").get_json()
    assert status["username_configured"] is False
    assert status["setup_required"] is True

    started = client.post(
        "/api/auth/start",
        json={
            "username": "person@example.com",
            "password": "temporary-apple-password",
            "admin_password": "strong-admin-password",
        },
    )
    assert started.status_code == 200
    verified = client.post(
        "/api/auth/verify",
        headers={"X-Admin-Password": "strong-admin-password"},
        json={"code": "123456"},
    )

    assert verified.status_code == 200
    assert identity_store.load() == "person@example.com"
    assert "temporary-apple-password" not in identity_store.path.read_text(encoding="utf-8")
    assert poller.auth.username == "person@example.com"


def test_weak_admin_password_requires_two_explicit_confirmations(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr("find_my_timeline.web.ICloudAuth", AuthStub)
    session_directory = tmp_path / "session"
    app = create_app(
        LocationDatabase(tmp_path / "locations.db"),
        None,
        PollerStub(),
        WebAdminStore(session_directory),
        AppleIdentityStore(session_directory),
    )
    app.config.update(TESTING=True)
    client = app.test_client()
    payload = {
        "username": "person@example.com",
        "password": "temporary-apple-password",
        "admin_password": "weak",
        "accept_weak_password_warning": True,
    }

    rejected = client.post("/api/auth/start", json=payload)
    assert rejected.status_code == 400

    payload["confirm_weak_password_warning"] = True
    accepted = client.post("/api/auth/start", json=payload)
    assert accepted.status_code == 200
