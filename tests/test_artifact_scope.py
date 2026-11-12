import json

import pytest

from services.artifact_scope import classify_path, load_policy


def test_artifact_policy_names_allowed_local_sources_and_prohibits_external_inputs():
    report = load_policy()
    assert report["status"] == "available"
    assert report["policy_sha256"]
    assert {
        "committed_public_mock_audio",
        "frozen_benchmark_evidence",
        "locally_cached_model_files",
        "installed_and_cached_dependencies",
        "committed_test_fixtures",
    } == set(report["permitted_categories"])
    with open(
        "evaluation/contracts/artifact-scope-v1.json", encoding="utf-8"
    ) as source:
        policy = json.load(source)
    assert "new_dataset_or_model_downloads" in policy["prohibited"]
    assert policy["clinical_release_authorized"] is False


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("evaluation/datasets/mock/manifest.json", "committed_public_mock_audio"),
        ("evaluation/reports/frozen.json", "frozen_benchmark_evidence"),
        ("data/models/local/model.bin", "locally_cached_model_files"),
        (
            "apps/clinician-web/node_modules/pkg/index.js",
            "installed_and_cached_dependencies",
        ),
        ("tests/test_contract.py", "committed_test_fixtures"),
    ],
)
def test_artifact_paths_are_classified_by_policy(path, category):
    assert classify_path(path)["category"] == category


def test_artifact_scope_rejects_path_escape_and_unclassified_inputs(tmp_path):
    with pytest.raises(ValueError, match="artifact_scope_path_escape"):
        classify_path("../patient/audio.wav", tmp_path)
    assert classify_path("patient/audio.wav")["status"] == "prohibited_or_unclassified"
