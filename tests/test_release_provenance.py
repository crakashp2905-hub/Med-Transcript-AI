import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from services.release_provenance import (
    build_acceptance_provenance,
    canonical_sha256,
    validate_release_candidate,
)
from services.ci_provenance import make_job_record


def _write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _json(root, relative, value):
    return _write(
        root,
        relative,
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )


def _candidate(root):
    root.mkdir(parents=True, exist_ok=True)
    source_sha = _write(root, "app.py", b"release source\n")
    _write(root, "data/manifest.json", b'{"dataset":"fixture-v1"}\n')
    _write(root, "data/protocol.json", b'{"protocol":"locked"}\n')
    manifest_sha = hashlib.sha256(
        (root / "data/manifest.json").read_bytes()
    ).hexdigest()
    protocol_sha = hashlib.sha256(
        (root / "data/protocol.json").read_bytes()
    ).hexdigest()
    _json(
        root,
        "data/lock.json",
        {"manifest_sha256": manifest_sha, "protocol_sha256": protocol_sha},
    )
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME="Local Test",
        GIT_AUTHOR_EMAIL="test@example.invalid",
    )
    env.update(
        GIT_COMMITTER_NAME="Local Test", GIT_COMMITTER_EMAIL="test@example.invalid"
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "app.py"], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "test source"], cwd=root, env=env, check=True
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    files = {"app.py": source_sha}
    code_body = {
        "schema_version": "code_manifest_v1",
        "source_commit": commit,
        "files": files,
    }
    code_digest = canonical_sha256(code_body)
    code_manifest = {**code_body, "manifest_sha256": code_digest}
    code_sha = _json(root, "code-manifest.json", code_manifest)
    acceptance_sha = None
    jobs = []
    for name in (
        "test-dev-security",
        "test-dev-asr-security",
        "frontend",
        "postgres",
        "container",
    ):
        log_path = f"logs/{name}.json"
        log_record = {
            "schema_version": "ci_job_log_binding_v1",
            "name": name,
            "run_id": "local-fixture-run",
            "source_commit": commit,
            "conclusion": "success",
            "code_manifest_sha256": code_digest,
            "dataset_manifests": [{"manifest_sha256": manifest_sha}],
        }
        log_sha = _json(root, log_path, log_record)
        jobs.append(
            {
                "name": name,
                "run_id": "local-fixture-run",
                "source_commit": commit,
                "conclusion": "success",
                "log_path": log_path,
                "log_sha256": log_sha,
            }
        )
    acceptance_sha = _json(
        root,
        "acceptance.json",
        {
            "source_commit": commit,
            "source_sha256": files,
            "code_manifest_sha256": code_digest,
            "checks": {name: {"status": "pass"} for name in ("core", "frontend")},
            "provenance": {
                "code_manifest_sha256": code_digest,
                "dataset_manifests": [{"manifest_sha256": manifest_sha}],
            },
        },
    )
    return {
        "schema_version": "release_candidate_binding_v1",
        "source_commit": commit,
        "code_manifest": {"path": "code-manifest.json", "sha256": code_sha},
        "acceptance_report": {"path": "acceptance.json", "sha256": acceptance_sha},
        "dataset_manifests": [
            {
                "manifest_path": "data/manifest.json",
                "manifest_sha256": manifest_sha,
                "protocol_path": "data/protocol.json",
                "protocol_sha256": protocol_sha,
                "lock_path": "data/lock.json",
                "lock_sha256": hashlib.sha256(
                    (root / "data/lock.json").read_bytes()
                ).hexdigest(),
            }
        ],
        "ci_run": {"run_id": "local-fixture-run", "jobs": jobs},
    }


def test_release_candidate_binds_exact_commit_code_data_acceptance_and_ci_logs(
    tmp_path,
):
    candidate = _candidate(tmp_path)
    result = validate_release_candidate(candidate, tmp_path)
    assert result["source_commit"] == candidate["source_commit"]
    assert result["ci_run_id"] == "local-fixture-run"
    assert len(result["ci_log_sha256"]) == 5
    assert result["real_patient_release_authorized"] is False
    assert len(result["binding_sha256"]) == 64


def test_release_candidate_rejects_acceptance_commit_mismatch(tmp_path):
    candidate = _candidate(tmp_path)
    report = json.loads((tmp_path / "acceptance.json").read_text())
    report["source_commit"] = "0" * 40
    candidate["acceptance_report"]["sha256"] = _json(
        tmp_path, "acceptance.json", report
    )
    with pytest.raises(ValueError, match="acceptance_commit_mismatch"):
        validate_release_candidate(candidate, tmp_path)


def test_release_candidate_rejects_mutated_code_against_git_tree(tmp_path):
    candidate = _candidate(tmp_path)
    (tmp_path / "app.py").write_bytes(b"changed after commit\n")
    candidate["code_manifest"]["sha256"] = hashlib.sha256(
        (tmp_path / "code-manifest.json").read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError, match="code_file_sha256_mismatch"):
        validate_release_candidate(candidate, tmp_path)


def test_release_candidate_requires_five_successful_same_run_ci_jobs(tmp_path):
    missing_root = tmp_path / "missing-jobs"
    candidate = _candidate(missing_root)
    candidate["ci_run"]["jobs"].pop()
    with pytest.raises(ValueError, match="ci_job_set_incomplete"):
        validate_release_candidate(candidate, missing_root)
    failed_root = tmp_path / "failed-job"
    candidate = _candidate(failed_root)
    candidate["ci_run"]["jobs"][0]["conclusion"] = "cancelled"
    with pytest.raises(ValueError, match="ci_job_not_successful"):
        validate_release_candidate(candidate, failed_root)


def test_release_candidate_rejects_log_metadata_not_matching_hashed_job_receipt(
    tmp_path,
):
    candidate = _candidate(tmp_path)
    job = candidate["ci_run"]["jobs"][0]
    _json(
        tmp_path,
        job["log_path"],
        {
            "schema_version": "ci_job_log_binding_v1",
            "name": job["name"],
            "run_id": "other-run",
            "source_commit": job["source_commit"],
            "conclusion": "success",
            "code_manifest_sha256": candidate["acceptance_report"]["sha256"],
            "dataset_manifests": [],
        },
    )
    with pytest.raises(ValueError, match="ci_log_sha256_mismatch"):
        validate_release_candidate(candidate, tmp_path)


def test_acceptance_provenance_records_exact_code_dataset_and_ci_context():
    commit = "a" * 40
    files = {"services/app.py": "b" * 64}
    datasets = [{"path": "evaluation/data/manifest.json", "sha256": "c" * 64}]
    result = build_acceptance_provenance(
        commit,
        files,
        datasets,
        {
            "run_id": "12345",
            "attempt": "2",
            "job": "frontend",
            "source_commit": commit,
        },
    )
    assert result["source_commit"] == commit
    assert result["dataset_manifests"][0]["manifest_sha256"] == "c" * 64
    assert result["ci_context"]["status"] == "observed_context_only"
    assert result["ci_context"]["run_id"] == "12345"
    assert len(result["code_manifest_sha256"]) == 64


def test_acceptance_provenance_rejects_ci_context_for_another_commit():
    with pytest.raises(ValueError, match="ci_context_commit_mismatch"):
        build_acceptance_provenance(
            "a" * 40,
            {"services/app.py": "b" * 64},
            [{"path": "data.json", "sha256": "c" * 64}],
            {"run_id": "123", "job": "core", "source_commit": "d" * 40},
        )


def test_ci_job_log_record_binds_run_commit_code_and_dataset_hashes():
    commit = "a" * 40
    result = make_job_record(
        {"source_commit": commit, "run_id": "run-42", "job": "frontend"},
        commit,
        {"apps/clinician-web/src/main.tsx": "b" * 64},
        "c" * 64,
    )
    assert result["schema_version"] == "ci_job_log_binding_v1"
    assert result["source_commit"] == commit
    assert result["code_manifest_sha256"]
    assert result["dataset_manifests"] == [
        {
            "path": "evaluation/datasets/meddistract-detailed-v1/manifest.json",
            "manifest_sha256": "c" * 64,
        }
    ]
    with pytest.raises(ValueError, match="ci_checkout_commit_mismatch"):
        make_job_record(
            {"source_commit": "d" * 40, "run_id": "run-42", "job": "frontend"},
            commit,
            {"apps/clinician-web/src/main.tsx": "b" * 64},
            "c" * 64,
        )


def test_ci_workflow_emits_receipts_after_all_five_job_lanes():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    ).read_text()
    assert workflow.count("python -m services.ci_provenance") == 4
    assert "test-dev-security" in workflow
    assert "test-dev-asr-security" in workflow
    frontend = workflow.split("  frontend:", 1)[1].split("  postgres:", 1)[0]
    assert "working-directory: ." in frontend
    for job in ("frontend", "postgres", "container"):
        assert f"MED_TRANSCRIPT_CI_JOB: {job}" in workflow
