import json
from pathlib import Path

from services.api.ingest import file_sha256


INVENTORY = Path("evaluation/reports/asr-asset-rights-inventory-v1.json")


def test_asset_rights_inventory_binds_all_frozen_evaluation_assets():
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    suite_path = Path(inventory["bindings"]["suite"])
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest_path = Path(inventory["bindings"]["dataset_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_rows = {row["candidate_id"]: row for row in inventory["models"]}

    assert inventory["schema_version"] == "asr_asset_rights_inventory_v1"
    assert file_sha256(suite_path) == inventory["bindings"]["suite_sha256"]
    assert (
        file_sha256(manifest_path) == inventory["bindings"]["dataset_manifest_sha256"]
    )
    assert set(model_rows) == {job["candidate_id"] for job in suite["jobs"]}
    assert manifest["rights_reviewed"] is True
    assert manifest["license"] == "CC-BY-4.0"

    for dataset in inventory["datasets"]:
        bound = (
            json.loads(Path(dataset["manifest"]).read_text(encoding="utf-8"))
            if dataset.get("manifest")
            else manifest
        )
        assert dataset["rights_reviewed_in_manifest"] is True
        assert dataset["license_declared"] in {"CC-BY-4.0", "MIT", "Apache-2.0"}
        assert dataset["manifest_sha256"] == file_sha256(
            Path(dataset.get("manifest") or manifest_path)
        )
        assert bound["source_revision"] == dataset["source_revision"]

    for job in suite["jobs"]:
        row = model_rows[job["candidate_id"]]
        assert row["access_state"] == "public_repository_no_access_gate_observed"
        assert row["license_declared"] in {"MIT", "CC-BY-4.0", "Apache-2.0"}
        assert row["license_source_url"].startswith("https://")
        if job.get("profile_id"):
            profile_path = Path(row["profile_file"])
            profile_file = json.loads(profile_path.read_text(encoding="utf-8"))
            profile = next(
                p for p in profile_file if p["profile_id"] == job["profile_id"]
            )
            assert file_sha256(profile_path) == row["profile_file_sha256"]
            assert profile["source"] == row["model_repository"]
            assert profile["revision"] == row["source_revision"]
            assert profile["license_id"] == row["license_declared"]
            assert profile["artifacts"] == row["artifact_sha256"]
        else:
            assert job["revision"] == row["source_revision"]
            assert job.get("expected_artifacts") == row["artifact_sha256"]
