"""Persistent password hashing for first-run WebUI administrator setup."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path


class WebAdminStore:
    """Store only a salted PBKDF2 hash in the persistent Apple session volume."""

    iterations = 600_000

    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory) if directory else Path.home() / ".find-my-timeline"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "web-admin.json"

    @property
    def configured(self) -> bool:
        return self.path.is_file()

    def prepare(self, password: str, *, allow_weak: bool = False) -> dict:
        if not password:
            raise ValueError("The WebUI administrator password must not be empty")
        if len(password) < 12 and not allow_weak:
            raise ValueError("The WebUI administrator password must contain at least 12 characters")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.iterations)
        return {
            "algorithm": "pbkdf2-sha256",
            "iterations": self.iterations,
            "salt": salt.hex(),
            "digest": digest.hex(),
        }

    def save(self, record: dict) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def verify(self, password: str, record: dict | None = None) -> bool:
        try:
            data = record or json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("algorithm") != "pbkdf2-sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(data["salt"]),
                int(data["iterations"]),
            )
            return hmac.compare_digest(digest.hex(), data["digest"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False
