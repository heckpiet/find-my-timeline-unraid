"""iCloud authentication module with 2FA support."""

from pathlib import Path
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException


class ICloudAuth:
    """Handles iCloud authentication including 2FA."""

    def __init__(self, username: str, password: str | None = None):
        self.username = username
        self.password = password
        self.api: PyiCloudService | None = None
        self._cookie_dir = Path.home() / ".find-my-timeline"
        self._cookie_dir.mkdir(exist_ok=True)

    def has_valid_session(self) -> bool:
        """Check if valid session cookies exist (without triggering 2FA)."""
        # Session files are named after username with special chars removed
        username_clean = self.username.replace("@", "").replace(".", "")
        session_file = self._cookie_dir / f"{username_clean}.session"
        cookie_file = self._cookie_dir / f"{username_clean}.cookiejar"
        return session_file.exists() and cookie_file.exists()

    def authenticate(self, allow_2fa: bool = True) -> PyiCloudService:
        """Authenticate with iCloud. Returns the API instance.

        Args:
            allow_2fa: If False, raises an error instead of prompting for 2FA.
                      Use this for non-interactive contexts like Docker.
        """
        try:
            self.api = PyiCloudService(
                self.username,
                self.password,
                cookie_directory=str(self._cookie_dir),
            )
        except PyiCloudFailedLoginException as e:
            raise AuthenticationError(f"Failed to login to iCloud: {e}") from e

        if self.api.requires_2fa:
            if not allow_2fa:
                raise AuthenticationError(
                    "2FA required but not allowed in non-interactive mode. "
                    "Run 'find-my-timeline auth' interactively first to create a session."
                )
            self._handle_2fa()
        elif self.api.requires_2sa:
            if not allow_2fa:
                raise AuthenticationError(
                    "2SA required but not allowed in non-interactive mode. "
                    "Run 'find-my-timeline auth' interactively first to create a session."
                )
            self._handle_2sa()

        return self.api

    def _handle_2fa(self) -> None:
        """Handle two-factor authentication."""
        print("Two-factor authentication required.")
        code = input("Enter the 2FA code sent to your trusted devices: ").strip()

        if not self.api.validate_2fa_code(code):
            raise AuthenticationError("Invalid 2FA code")

        print("2FA authentication successful!")

        # Trust this session
        if not self.api.is_trusted_session:
            print("Session is not trusted. Requesting trust...")
            if self.api.trust_session():
                print("Session trusted successfully.")
            else:
                print("Warning: Failed to trust session. You may need to re-authenticate sooner.")

    def _handle_2sa(self) -> None:
        """Handle two-step authentication (legacy)."""
        print("Two-step authentication required.")
        devices = self.api.trusted_devices

        print("Trusted devices:")
        for i, device in enumerate(devices):
            name = device.get("deviceName", f"Device {i}")
            print(f"  {i}: {name}")

        device_idx = int(input("Select device to receive verification code: ").strip())
        device = devices[device_idx]

        if not self.api.send_verification_code(device):
            raise AuthenticationError("Failed to send verification code")

        code = input("Enter the verification code: ").strip()

        if not self.api.validate_verification_code(device, code):
            raise AuthenticationError("Invalid verification code")

        print("2SA authentication successful!")

    def get_devices(self) -> list[dict]:
        """Get all devices from Find My iPhone service."""
        if not self.api:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")

        devices = []
        for device in self.api.devices:
            # AppleDevice has .location property and .data for raw content
            location = device.location
            data = device.data

            devices.append({
                "id": data.get("id", "unknown"),
                "name": data.get("name", "Unknown Device"),
                "device_display_name": data.get("deviceDisplayName", "Unknown"),
                "device_class": data.get("deviceClass", "unknown"),
                "battery_level": data.get("batteryLevel"),
                "battery_status": data.get("batteryStatus"),
                "location": location,
            })

        return devices


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass
