import pytest

from find_my_timeline.auth import AuthenticationError, ICloudAuth


class TrustedDeviceApi:
    trusted_devices = [{"deviceName": "Peter's private iPhone"}]

    def send_verification_code(self, _device):
        return True

    def validate_verification_code(self, _device, _code):
        return True


def test_two_step_authentication_does_not_print_private_device_names(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("find_my_timeline.auth.Path.home", lambda: tmp_path)
    responses = iter(["0", "123456"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))
    auth = ICloudAuth("demo@example.com")
    auth.api = TrustedDeviceApi()

    auth._handle_2sa()

    output = capsys.readouterr().out
    assert "Trusted device 1" in output
    assert "Peter's private iPhone" not in output


class WebTwoStepApi:
    requires_2sa = True
    requires_2fa = False
    trusted_devices = [
        {"deviceName": "Private phone"},
        {"phoneNumber": "+49 private"},
    ]

    def __init__(self):
        self.sent_device = None
        self.validated = None

    def send_verification_code(self, device):
        self.sent_device = device
        return True

    def validate_verification_code(self, device, code):
        self.validated = (device, code)
        return True


def test_web_two_step_flow_uses_sanitized_device_labels(monkeypatch, tmp_path):
    monkeypatch.setattr("find_my_timeline.auth.Path.home", lambda: tmp_path)
    api = WebTwoStepApi()
    auth = ICloudAuth("demo@example.com")
    monkeypatch.setattr(auth, "_create_service", lambda _password: api)

    result = auth.begin_web_authentication("not-stored")

    assert result == {
        "requires_2fa": False,
        "requires_2sa": True,
        "status": "waiting_for_device",
        "trusted_devices": [
            {"index": 0, "label": "Trusted device 1"},
            {"index": 1, "label": "Trusted device 2"},
        ],
    }
    assert "Private phone" not in str(result)
    with pytest.raises(AuthenticationError, match="valid trusted device"):
        auth.send_web_2sa_code(3)

    auth.send_web_2sa_code(1)
    auth.complete_web_2sa("123456")

    assert api.sent_device == api.trusted_devices[1]
    assert api.validated == (api.trusted_devices[1], "123456")
    assert auth.authentication_metadata()["state"] == "valid"
