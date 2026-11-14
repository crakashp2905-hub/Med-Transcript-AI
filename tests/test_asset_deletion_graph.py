import json
from pathlib import Path


def test_asset_deletion_graph_covers_required_local_data_and_honest_limits():
    graph = json.loads(
        Path("evaluation/contracts/asset-deletion-graph-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assets = {asset["id"]: asset for asset in graph["assets"]}

    assert {
        "original_audio",
        "normalized_audio",
        "live_audio_prefix",
        "transcript",
        "clinical_note",
        "preview_cache",
        "model_proposals",
        "exports",
        "asr_checkpoints",
        "authorizations",
        "idempotency",
        "audit_metadata",
    } <= assets.keys()
    assert graph["primary_purge"]["holds"] == ["legal_hold", "existing approval"]
    assert graph["primary_purge"]["backup_expiry"] == "requires_operator_confirmation"
    assert any(
        edge["from"] == "primary_purge" and edge["to"] == "backup_tombstone"
        for edge in graph["edges"]
    )
    assert graph["clinical_release_authorized"] is False
    assert graph["limitations"]
