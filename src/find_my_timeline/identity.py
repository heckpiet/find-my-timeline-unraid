"""Persistent non-secret Apple account identity for WebUI onboarding."""

from __future__ import annotations

import json
import os
from pathlib import Path


class AppleIdentityStore:
    """Persist only the Apple ID address in the protected session directory."""

    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory) if directory else Path.home() / ".find-my-timeline"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "apple-identity.json"

    def load(self) -> str | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            username = str(data.get("username", "")).strip()
            return username or None
        except (OSError, TypeError, json.JSONDecodeError):
            return None

    def save(self, username: str) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"username": username}, indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)
