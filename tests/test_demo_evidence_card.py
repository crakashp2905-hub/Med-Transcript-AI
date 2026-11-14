import json
from pathlib import Path

from tests.test_foundation import headers


def test_demo_case_response_binds_public_source_hash_and_scope(environment):
    response = environment.client.get("/v1/demo-cases", headers=headers())
    assert response.status_code == 200
    body = response.json()
    assert (
        "source hashes bind the selected audio to the local manifest" in body["scope"]
    )
    manifest = json.loads(
        Path("evaluation/datasets/meddistract-detailed-v1/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    clean = {
        case["group_id"]: case["audio_sha256"]
        for case in manifest["cases"]
        if case["condition"] == "clean"
    }
    assert body["items"]
    assert all(item["source_sha256"] == clean[item["id"]] for item in body["items"])
