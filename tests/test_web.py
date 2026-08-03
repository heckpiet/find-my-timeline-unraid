from find_my_timeline.database import LocationDatabase
from find_my_timeline.web import create_app


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


class AuthStub:
    username = "person@example.com"
    password = None

    def authentication_metadata(self, lifetime_days):
        return {"configured": True, "state": "valid", "remaining_days": lifetime_days}

    def begin_web_authentication(self, password):
        return {"requires_2fa": True, "status": "waiting_for_code"}

    def complete_web_2fa(self, code):
        return None

    def get_devices(self):
        return []


def make_client(tmp_path, monkeypatch, with_auth=False):
    monkeypatch.setenv("WEB_AUTH_ENABLED", "true" if with_auth else "false")
    monkeypatch.setenv("WEB_ADMIN_PASSWORD", "test-admin-password" if with_auth else "")
    database = LocationDatabase(tmp_path / "locations.db")
    poller = PollerStub()
    app = create_app(database, AuthStub() if with_auth else None, poller)
    app.config.update(TESTING=True)
    return app.test_client(), poller


def test_health_and_system_status(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)

    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    response = client.get("/api/system/status")
    assert response.status_code == 200
    assert response.get_json()["poller"]["state"] == "running"


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
