from datetime import datetime, timezone

from find_my_timeline.database import LocationDatabase


def test_location_timestamp_is_normalized_and_detected_as_duplicate(tmp_path):
    database = LocationDatabase(tmp_path / "locations.db")
    database.upsert_device("phone", "Demo phone")
    timestamp = datetime(2026, 8, 3, 20, 30, tzinfo=timezone.utc)

    assert not database.location_exists("phone", timestamp)
    database.record_location("phone", 52.5, 13.4, timestamp)

    assert database.location_exists("phone", timestamp)
    assert database.get_latest_location("phone")["timestamp"] == timestamp.isoformat()


def test_naive_timestamp_is_treated_as_utc(tmp_path):
    database = LocationDatabase(tmp_path / "locations.db")
    database.upsert_device("phone", "Demo phone")
    timestamp = datetime(2026, 8, 3, 20, 30)

    database.record_location("phone", 52.5, 13.4, timestamp)

    assert database.get_latest_location("phone")["timestamp"].endswith("+00:00")
