"""Emit a structured, exact-commit provenance record as a CI log line."""

import json
import os
import subprocess
from pathlib import Path

from services.engineering_status import sha256
from services.offline_acceptance import source_inventory
from services.release_provenance import build_acceptance_provenance


DATASET_MANIFEST = Path("evaluation/datasets/meddistract-detailed-v1/manifest.json")
DATASET_PROTOCOL = Path("evaluation/datasets/meddistract-detailed-v1/protocol.json")
DATASET_LOCK = Path("evaluation/datasets/meddistract-detailed-v1/lock.json")


def make_job_record(context, actual_commit, source_files, dataset_manifest_sha256):
    expected_commit = context.get("source_commit")
    if not expected_commit or expected_commit != actual_commit:
        raise ValueError("ci_checkout_commit_mismatch")
    if not context.get("run_id") or not context.get("job"):
        raise ValueError("ci_context_incomplete")
    provenance = build_acceptance_provenance(
        actual_commit,
        source_files,
        [{"path": DATASET_MANIFEST.as_posix(), "sha256": dataset_manifest_sha256}],
        {
            "provider": "github-actions",
            "run_id": context["run_id"],
            "attempt": context.get("attempt"),
            "job": context["job"],
            "workflow": context.get("workflow"),
            "ref": context.get("ref"),
            "source_commit": actual_commit,
        },
    )
    return {
        "schema_version": "ci_job_log_binding_v1",
        "name": context["job"],
        "run_id": context["run_id"],
        "source_commit": actual_commit,
        "conclusion": "success",
        "code_manifest_sha256": provenance["code_manifest_sha256"],
        "dataset_manifests": provenance["dataset_manifests"],
    }


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    actual_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    context = {
        "source_commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "job": os.environ.get("MED_TRANSCRIPT_CI_JOB") or os.environ.get("GITHUB_JOB"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "ref": os.environ.get("GITHUB_REF"),
    }
    lock = json.loads(DATASET_LOCK.read_text(encoding="utf-8"))
    if sha256(DATASET_MANIFEST) != lock.get("manifest_sha256"):
        raise ValueError("ci_dataset_manifest_mismatch")
    if sha256(DATASET_PROTOCOL) != lock.get("protocol_sha256"):
        raise ValueError("ci_dataset_protocol_mismatch")
    record = make_job_record(
        context,
        actual_commit,
        source_inventory(),
        lock["manifest_sha256"],
    )
    print("MED_TRANSCRIPT_CI_PROVENANCE=" + json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
