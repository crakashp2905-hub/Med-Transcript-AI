import hashlib
from pathlib import Path
import pytest
from services.offline_preflight import inventory_artifact_tree, inventory_models


def test_model_inventory_hashes_bytes_without_claiming_model_eligibility(tmp_path):
    model = tmp_path / "data/models/fixture"
    model.mkdir(parents=True)
    artifact = model / "model.bin"
    artifact.write_bytes(b"not-a-real-model")
    report = inventory_models(tmp_path, True)
    assert report[0]["files"] == [
        {
            "path": "data/models/fixture/model.bin",
            "bytes": 16,
            "sha256": hashlib.sha256(b"not-a-real-model").hexdigest(),
        }
    ]
    assert report[0]["status"] == "contents_hashed_not_model_eligibility"
    artifact.write_bytes(b"changed-artifact")
    assert (
        inventory_models(tmp_path, True)[0]["files"][0]["sha256"]
        != report[0]["files"][0]["sha256"]
    )
    assert (
        inventory_models(tmp_path, False)[0]["status"]
        == "directory_present_not_a_weight_verification"
    )
    assert inventory_models(tmp_path / "absent", True) == []


def test_model_inventory_rejects_files_that_change_during_streaming(
    tmp_path, monkeypatch
):
    import services.offline_preflight as module

    model = tmp_path / "data/models/fixture"
    model.mkdir(parents=True)
    artifact = model / "model.bin"
    artifact.write_bytes(b"initial")
    original = module.sha256

    def mutate(path):
        digest = original(path)
        path.write_bytes(b"changed-after-hash")
        return digest

    monkeypatch.setattr(module, "sha256", mutate)
    with pytest.raises(ValueError, match="model_changed_during_inventory"):
        inventory_models(tmp_path, True)


def test_cache_inventory_hashes_root_files_and_nested_artifacts(tmp_path):
    cache = tmp_path / "data/models"
    (cache / "model").mkdir(parents=True)
    (cache / "model/weights.bin").write_bytes(b"weight")
    (cache / "archive.tar").write_bytes(b"archive")
    report = inventory_artifact_tree(tmp_path, "data/models")
    assert report["status"] == "contents_hashed"
    assert [item["path"] for item in report["files"]] == [
        "data/models/archive.tar",
        "data/models/model/weights.bin",
    ]
    assert report["total_bytes"] == 13


def test_cache_inventory_reports_missing_cache(tmp_path):
    report = inventory_artifact_tree(tmp_path, "data/wheelhouse")
    assert report["status"] == "blocked_missing_local_artifact"
    assert report["files"] == []


def test_cache_inventory_rejects_symlinks(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "outside").write_bytes(b"external")
    original = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path.name == "outside" or original(path),
    )
    with pytest.raises(ValueError, match="artifact_inventory_symlink_or_escape"):
        inventory_artifact_tree(tmp_path, "cache")


def test_runtime_profile_loader_rejects_unpinned_manifest(tmp_path):
    from services.asr.profiles import load_runtime_profiles

    manifest = tmp_path / "profiles.json"
    manifest.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="not_allowlisted"):
        load_runtime_profiles(manifest)


def test_runtime_profile_loader_accepts_pinned_local_manifest():
    from services.asr.profiles import load_runtime_profiles

    profiles = load_runtime_profiles("data/asr-smoke-profiles.json")
    assert set(profiles) == {"tiny-en-smoke-v1"}
