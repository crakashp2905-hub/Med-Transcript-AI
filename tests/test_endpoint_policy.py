from services.endpoint_policy import validate


def test_endpoint_policy_rejects_private_destinations_in_offline_mode():
    assert (
        validate("http://127.0.0.1:8000", offline=True)["reason"]
        == "private_destination"
    )
    assert validate("http://service.local", offline=True)["allowed"] is False


def test_endpoint_policy_accepts_public_https_endpoint():
    assert validate("https://provider.example.com", offline=True)["allowed"] is True
