from find_my_timeline.identity import AppleIdentityStore


def test_identity_store_persists_only_username(tmp_path):
    store = AppleIdentityStore(tmp_path)

    store.save("person@example.com")

    assert store.load() == "person@example.com"
    assert store.path.name == "apple-identity.json"
