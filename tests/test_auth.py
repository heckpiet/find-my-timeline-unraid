from find_my_timeline.auth import ICloudAuth


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
