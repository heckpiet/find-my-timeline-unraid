"""Location polling service with random intervals."""

import logging
import random
import signal
import time
from datetime import datetime, timezone
from threading import Event, RLock
from typing import Callable

from .auth import AuthenticationError, ICloudAuth
from .database import LocationDatabase

logger = logging.getLogger(__name__)


class LocationPoller:
    """Polls device locations at random intervals and stores them."""

    def __init__(
        self,
        auth: ICloudAuth,
        database: LocationDatabase,
        min_interval: int = 7,
        max_interval: int = 10,
        auth_retry_interval: int = 5,
    ):
        self.auth = auth
        self.database = database
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.auth_retry_interval = auth_retry_interval
        self._running = False
        self._on_poll_callbacks: list[Callable[[list[dict]], None]] = []
        self._wake_event = Event()
        self._status_lock = RLock()
        self._status = {
            "state": "stopped",
            "last_attempt_at": None,
            "last_success_at": None,
            "next_poll_at": None,
            "last_error": None,
        }

    def on_poll(self, callback: Callable[[list[dict]], None]) -> None:
        """Register a callback to be called after each poll."""
        self._on_poll_callbacks.append(callback)

    def _get_next_interval(self) -> float:
        """Get a random interval between min and max (in minutes)."""
        return random.uniform(self.min_interval, self.max_interval) * 60

    def status(self) -> dict:
        """Return a thread-safe snapshot of the poller state."""
        with self._status_lock:
            return dict(self._status)

    def wake(self) -> None:
        """Wake the poller so a renewed Apple session is used immediately."""
        self._wake_event.set()

    def _set_status(self, **changes) -> None:
        with self._status_lock:
            self._status.update(changes)

    def _wait(self, seconds: float) -> None:
        self._wake_event.wait(max(0, seconds))
        self._wake_event.clear()

    def poll_once(self) -> list[dict]:
        """Poll all devices once and store locations. Returns the recorded locations."""
        devices = self.auth.get_devices()

        recorded = []

        for device in devices:
            device_id = device["id"]
            location = device.get("location")

            # Update device info
            self.database.upsert_device(
                device_id=device_id,
                name=device["name"],
                device_display_name=device.get("device_display_name"),
                device_class=device.get("device_class"),
            )

            if not location:
                logger.warning("No location available for device %s", device["name"])
                continue

            latitude = location.get("latitude")
            longitude = location.get("longitude")

            if latitude is None or longitude is None:
                logger.warning("Invalid coordinates for device %s", device["name"])
                continue

            # Parse timestamp (Apple returns milliseconds since epoch)
            timestamp_ms = location.get("timeStamp")
            if timestamp_ms:
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)
            elif location.get("isOld", False):
                # Skip if location is marked as old/stale and no timestamp
                logger.info("Skipping stale location for %s", device["name"])
                continue
            else:
                timestamp = datetime.now(timezone.utc)

            if self.database.location_exists(device_id, timestamp):
                logger.debug("Skipping duplicate location for %s", device["name"])
                continue

            # Record the location
            location_id = self.database.record_location(
                device_id=device_id,
                latitude=latitude,
                longitude=longitude,
                timestamp=timestamp,
                horizontal_accuracy=location.get("horizontalAccuracy"),
                position_type=location.get("positionType"),
                battery_level=device.get("battery_level"),
            )

            recorded_location = {
                "id": location_id,
                "device_id": device_id,
                "device_name": device["name"],
                "latitude": latitude,
                "longitude": longitude,
                "timestamp": timestamp.isoformat(),
                "accuracy": location.get("horizontalAccuracy"),
                "position_type": location.get("positionType"),
                "battery_level": device.get("battery_level"),
            }
            recorded.append(recorded_location)

            logger.info("Recorded a new location for %s at %s", device["name"], timestamp)

        # Call registered callbacks
        for callback in self._on_poll_callbacks:
            try:
                callback(recorded)
            except Exception:
                logger.exception("Poll callback failed")

        return recorded

    def start(self, setup_signals: bool = True, allow_2fa: bool = False) -> None:
        """Start the polling loop. Blocks until stopped.

        Args:
            setup_signals: Whether to set up signal handlers (only works in main thread)
            allow_2fa: If False (default), refuses to prompt for 2FA interactively.
                      This prevents lockouts in non-interactive contexts like Docker.
        """
        self._running = True
        self._set_status(state="starting", last_error=None, next_poll_at=None)

        # Set up signal handlers for graceful shutdown (only in main thread)
        if setup_signals:
            try:

                def handle_signal(signum, frame):
                    logger.info("Received signal %s, stopping...", signum)
                    self._running = False

                signal.signal(signal.SIGINT, handle_signal)
                signal.signal(signal.SIGTERM, handle_signal)
            except ValueError:
                # Signal only works in main thread - skip if in background thread
                pass

        logger.info(
            "Starting location poller (interval: %d-%d minutes)",
            self.min_interval,
            self.max_interval,
        )

        while self._running:
            now = datetime.now(timezone.utc).isoformat()
            self._set_status(state="authenticating", last_attempt_at=now, next_poll_at=None)
            try:
                if self.auth.api is None:
                    self.auth.authenticate(allow_2fa=allow_2fa)
                recorded = self.poll_once()
                completed_at = datetime.now(timezone.utc)
                interval = self._get_next_interval()
                next_poll_at = datetime.fromtimestamp(
                    completed_at.timestamp() + interval, timezone.utc
                )
                self._set_status(
                    state="running",
                    last_success_at=completed_at.isoformat(),
                    next_poll_at=next_poll_at.isoformat(),
                    last_error=None,
                )
                logger.info("Poll successful; recorded %d location(s)", len(recorded))
                logger.info(
                    "Next poll in %.1f minutes (at %s)",
                    interval / 60,
                    next_poll_at.astimezone().strftime("%H:%M:%S"),
                )
                self._wait(interval)
            except Exception as exc:
                # A failed or expired session must not terminate the background
                # service. Clear it, report the degraded state, and retry later.
                self.auth.api = None
                retry_seconds = max(1, self.auth_retry_interval) * 60
                retry_at = datetime.fromtimestamp(time.time() + retry_seconds, timezone.utc)
                public_error = (
                    str(exc)
                    if isinstance(exc, AuthenticationError)
                    else "Apple service or network request failed"
                )
                self._set_status(
                    state="waiting_for_authentication",
                    last_error=public_error,
                    next_poll_at=retry_at.isoformat(),
                )
                logger.error(
                    "Polling unavailable: %s; retrying in %d minute(s)",
                    exc,
                    self.auth_retry_interval,
                )
                self._wait(retry_seconds)

        self._set_status(state="stopped", next_poll_at=None)
        logger.info("Poller stopped")

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        self._wake_event.set()
