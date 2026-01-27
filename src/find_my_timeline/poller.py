"""Location polling service with random intervals."""

import logging
import random
import signal
import time
from datetime import datetime
from typing import Callable

from .auth import ICloudAuth, AuthenticationError
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
    ):
        self.auth = auth
        self.database = database
        self.min_interval = min_interval
        self.max_interval = max_interval
        self._running = False
        self._on_poll_callbacks: list[Callable[[list[dict]], None]] = []

    def on_poll(self, callback: Callable[[list[dict]], None]) -> None:
        """Register a callback to be called after each poll."""
        self._on_poll_callbacks.append(callback)

    def _get_next_interval(self) -> float:
        """Get a random interval between min and max (in minutes)."""
        return random.uniform(self.min_interval, self.max_interval) * 60

    def poll_once(self) -> list[dict]:
        """Poll all devices once and store locations. Returns the recorded locations."""
        try:
            devices = self.auth.get_devices()
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")
            return []

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
                logger.warning(f"No location available for device {device['name']}")
                continue

            latitude = location.get("latitude")
            longitude = location.get("longitude")

            if latitude is None or longitude is None:
                logger.warning(f"Invalid coordinates for device {device['name']}")
                continue

            # Parse timestamp (Apple returns milliseconds since epoch)
            timestamp_ms = location.get("timeStamp")
            if timestamp_ms:
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
            elif location.get("isOld", False):
                # Skip if location is marked as old/stale and no timestamp
                logger.info(f"Skipping stale location for {device['name']}")
                continue
            else:
                timestamp = datetime.now()

            # Check if this is a duplicate (same timestamp as last recorded)
            last_location = self.database.get_latest_location(device_id)
            if last_location:
                last_ts = last_location.get("timestamp")
                if last_ts and str(last_ts) == str(timestamp):
                    logger.debug(f"Skipping duplicate location for {device['name']}")
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

            logger.info(
                f"Recorded location for {device['name']}: "
                f"({latitude:.6f}, {longitude:.6f}) at {timestamp}"
            )

        # Call registered callbacks
        for callback in self._on_poll_callbacks:
            try:
                callback(recorded)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return recorded

    def start(self, setup_signals: bool = True, allow_2fa: bool = False) -> None:
        """Start the polling loop. Blocks until stopped.

        Args:
            setup_signals: Whether to set up signal handlers (only works in main thread)
            allow_2fa: If False (default), refuses to prompt for 2FA interactively.
                      This prevents lockouts in non-interactive contexts like Docker.
        """
        self._running = True

        # Set up signal handlers for graceful shutdown (only in main thread)
        if setup_signals:
            try:
                def handle_signal(signum, frame):
                    logger.info(f"Received signal {signum}, stopping...")
                    self._running = False

                signal.signal(signal.SIGINT, handle_signal)
                signal.signal(signal.SIGTERM, handle_signal)
            except ValueError:
                # Signal only works in main thread - skip if in background thread
                pass

        logger.info(
            f"Starting location poller (interval: {self.min_interval}-{self.max_interval} minutes)"
        )

        # Authenticate (don't allow 2FA by default to prevent lockouts in Docker)
        try:
            self.auth.authenticate(allow_2fa=allow_2fa)
            logger.info("Authentication successful")
        except AuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            return

        # Initial poll
        self.poll_once()

        while self._running:
            interval = self._get_next_interval()
            next_poll = datetime.now().timestamp() + interval
            next_poll_time = datetime.fromtimestamp(next_poll).strftime("%H:%M:%S")

            logger.info(f"Next poll in {interval/60:.1f} minutes (at {next_poll_time})")

            # Sleep in small increments to allow for graceful shutdown
            sleep_end = time.time() + interval
            while self._running and time.time() < sleep_end:
                time.sleep(min(1, sleep_end - time.time()))

            if self._running:
                self.poll_once()

        logger.info("Poller stopped")

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
