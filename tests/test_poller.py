import time
from threading import Thread

from find_my_timeline.auth import AuthenticationError
from find_my_timeline.database import LocationDatabase
from find_my_timeline.poller import LocationPoller


class RecoveringAuth:
    def __init__(self):
        self.api = None
        self.available = False
        self.authentication_attempts = 0

    def authenticate(self, allow_2fa=False):
        self.authentication_attempts += 1
        if not self.available:
            raise AuthenticationError("Two-factor authentication is required")
        self.api = object()
        return self.api

    def get_devices(self):
        return []


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_poller_recovers_after_authentication_without_restart(tmp_path):
    auth = RecoveringAuth()
    database = LocationDatabase(tmp_path / "locations.db")
    poller = LocationPoller(auth, database, auth_retry_interval=60)
    thread = Thread(target=poller.start, kwargs={"setup_signals": False}, daemon=True)

    thread.start()
    wait_until(lambda: poller.status()["state"] == "waiting_for_authentication")

    auth.available = True
    poller.wake()
    wait_until(lambda: poller.status()["last_success_at"] is not None)

    assert poller.status()["state"] == "running"
    assert auth.authentication_attempts >= 2

    poller.stop()
    thread.join(timeout=1)


def test_poller_waits_for_webui_setup_without_credentials(tmp_path):
    database = LocationDatabase(tmp_path / "locations.db")
    poller = LocationPoller(None, database, auth_retry_interval=60)
    thread = Thread(target=poller.start, kwargs={"setup_signals": False}, daemon=True)

    thread.start()
    wait_until(lambda: poller.status()["state"] == "waiting_for_setup")

    assert poller.status()["last_error"] == "Complete Apple setup in the WebUI"
    poller.stop()
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert poller.status()["state"] == "stopped"
