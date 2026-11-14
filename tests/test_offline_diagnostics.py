import hashlib
import json

from services.offline_diagnostics import (
    configured_model_directories,
    latest_acceptance,
    permission_probe,
)


def test_model_directory_inventory_distinguishes_missing_and_unconfigured(tmp_path):
    (tmp_path / "evaluation").mkdir()
    (tmp_path / "data/models/present").mkdir(parents=True)
    (tmp_path / "evaluation/detailed-suite-v7.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {"candidate_id": "present-model", "model_dir": "data/models/present"},
                    {"candidate_id": "missing-model", "model_dir": "data/models/missing"},
                    {"candidate_id": "cached-runtime"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = configured_model_directories(tmp_path)

    assert result["status"] == "measured"
    assert result["present"][0]["candidate_ids"] == ["present-model"]
    assert result["missing"][0]["candidate_ids"] == ["missing-model"]
    assert result["unconfigured_candidate_ids"] == ["cached-runtime"]


def test_permission_probe_reports_access_and_leaves_no_probe_file(tmp_path):
    result = permission_probe(tmp_path)

    assert result == {
        "path": tmp_path.as_posix(),
        "exists": True,
        "readable": True,
        "writable_probe": True,
    }
    assert list(tmp_path.iterdir()) == []


def test_latest_acceptance_verifies_report_hash_and_surfaces_blocked_tests(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "evaluation/reports").mkdir(parents=True)
    report_path = tmp_path / "evaluation/reports/acceptance.json"
    report_path.write_text(
        json.dumps(
            {
                "checks": {
                    "backend_tests": {
                        "status": "fail",
                        "detail": {
                            "test_result": {
                                "failed_test_ids": ["tests/test_api.py::test_contract"],
                                "skipped_tests": [{"path": "tests/test_media.py"}],
                            }
                        },
                    },
                    "source_integrity": {"status": "pass"},
                }
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    (tmp_path / "data/offline-acceptance-summary.json").write_text(
        json.dumps({"report": "evaluation/reports/acceptance.json", "sha256": digest}),
        encoding="utf-8",
    )

    result = latest_acceptance(tmp_path)

    assert result["status"] == "available"
    assert result["blocked_checks"] == ["backend_tests"]
    assert result["failed_tests"] == ["tests/test_api.py::test_contract"]
    assert result["skipped_tests"] == [{"path": "tests/test_media.py"}]


def test_latest_acceptance_rejects_report_hash_mismatch(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "evaluation/reports").mkdir(parents=True)
    (tmp_path / "evaluation/reports/acceptance.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data/offline-acceptance-summary.json").write_text(
        json.dumps({"report": "evaluation/reports/acceptance.json", "sha256": "0" * 64}),
        encoding="utf-8",
    )

    assert latest_acceptance(tmp_path)["status"] == "invalid_or_unavailable"
