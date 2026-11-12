from pathlib import Path


def test_compose_security_contract_is_restricted_and_private():
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    production = Path("compose.production.yaml").read_text(encoding="utf-8")
    for marker in (
        "read_only: true",
        "cap_drop: [ALL]",
        "security_opt: [no-new-privileges:true]",
        "internal: true",
        "mem_limit:",
        "pids_limit:",
    ):
        assert marker in compose
    assert "google_client_secret" in production and "POSTGRES_PASSWORD" in compose
