import pytest

from find_my_timeline.config import AppConfig, ConfigurationError


def test_config_parses_and_exposes_only_public_values():
    config = AppConfig.from_env(
        {
            "ICLOUD_USERNAME": "person@example.com",
            "ICLOUD_PASSWORD": "not-public",
            "POLL_MIN_INTERVAL": "8",
            "POLL_MAX_INTERVAL": "12",
            "WEB_AUTH_DISABLED": "yes",
            "WEB_ADMIN_PASSWORD": "also-not-public",
            "TZ": "UTC",
        }
    )

    assert config.username == "person@example.com"
    assert config.min_interval == 8
    assert config.max_interval == 12
    assert config.public_web_settings() == {
        "poll_min_interval": 8,
        "poll_max_interval": 12,
        "auth_retry_interval": 5,
        "timezone": "UTC",
        "web_auth_enabled": False,
    }
    assert "not-public" not in repr(config.public_web_settings())


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"POLL_MIN_INTERVAL": "invalid"}, "must be an integer"),
        ({"POLL_MIN_INTERVAL": "20", "POLL_MAX_INTERVAL": "10"}, "must not be greater"),
        ({"WEB_PORT": "70000"}, "must be between"),
        ({"WEB_AUTH_DISABLED": "sometimes"}, "must be true or false"),
    ],
)
def test_config_rejects_invalid_values(environment, message):
    with pytest.raises(ConfigurationError, match=message):
        AppConfig.from_env(environment)
