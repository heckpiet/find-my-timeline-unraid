import pytest

from find_my_timeline.web_admin import WebAdminStore


def test_web_admin_store_hashes_and_verifies_password(tmp_path):
    store = WebAdminStore(tmp_path)
    password = "a-strong-local-password"

    record = store.prepare(password)
    store.save(record)

    assert store.configured
    assert store.verify(password)
    assert not store.verify("incorrect-password")
    assert password not in store.path.read_text(encoding="utf-8")


def test_web_admin_store_rejects_short_password(tmp_path):
    store = WebAdminStore(tmp_path)

    with pytest.raises(ValueError, match="at least 12"):
        store.prepare("too-short")
