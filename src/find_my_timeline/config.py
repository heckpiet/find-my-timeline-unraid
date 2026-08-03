"""Typed application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when an environment variable contains an invalid value."""


def _integer(
    environ: Mapping[str, str],
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _boolean(environ: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = environ.get(name, str(default)).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false, got {raw!r}")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Validated runtime configuration shared by CLI, poller and WebUI."""

    username: str | None
    password: str | None
    min_interval: int
    max_interval: int
    auth_retry_interval: int
    db_path: Path
    web_host: str
    web_port: int
    web_auth_disabled: bool
    web_admin_password: str
    auth_session_lifetime_days: int
    web_auth_flow_timeout_seconds: int
    timezone: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> AppConfig:
        values = os.environ if environ is None else environ
        min_interval = _integer(values, "POLL_MIN_INTERVAL", 7, minimum=1, maximum=1440)
        max_interval = _integer(values, "POLL_MAX_INTERVAL", 10, minimum=1, maximum=1440)
        if min_interval > max_interval:
            raise ConfigurationError("POLL_MIN_INTERVAL must not be greater than POLL_MAX_INTERVAL")
        return cls(
            username=values.get("ICLOUD_USERNAME") or None,
            password=values.get("ICLOUD_PASSWORD") or None,
            min_interval=min_interval,
            max_interval=max_interval,
            auth_retry_interval=_integer(
                values, "AUTH_RETRY_INTERVAL_MINUTES", 5, minimum=1, maximum=1440
            ),
            db_path=Path(values.get("DATABASE_PATH", "./data/locations.db")),
            web_host=values.get("WEB_HOST", "127.0.0.1"),
            web_port=_integer(values, "WEB_PORT", 5000, minimum=1, maximum=65535),
            web_auth_disabled=_boolean(values, "WEB_AUTH_DISABLED"),
            web_admin_password=values.get("WEB_ADMIN_PASSWORD", ""),
            auth_session_lifetime_days=_integer(
                values, "AUTH_SESSION_LIFETIME_DAYS", 90, minimum=1, maximum=3650
            ),
            web_auth_flow_timeout_seconds=_integer(
                values, "WEB_AUTH_FLOW_TIMEOUT_SECONDS", 600, minimum=60, maximum=3600
            ),
            timezone=values.get("TZ", "Europe/Berlin"),
        )

    def public_web_settings(self) -> dict[str, int | str | bool]:
        """Return non-secret values that are safe to expose in the WebUI."""
        return {
            "poll_min_interval": self.min_interval,
            "poll_max_interval": self.max_interval,
            "auth_retry_interval": self.auth_retry_interval,
            "timezone": self.timezone,
            "web_auth_enabled": not self.web_auth_disabled,
        }
