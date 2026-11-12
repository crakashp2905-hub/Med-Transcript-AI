"""Build a model-free reproducibility manifest from committed artifacts."""

import hashlib
from pathlib import Path


def build(root="."):
    root = Path(root).resolve()
    names = [
        "pyproject.toml",
        "constraints-ci.txt",
        "evaluation/reports/engineering-baseline.json",
        "evaluation/reports/engineering-task-status.json",
        "docs/demo-runbook-offline.md",
    ]
    artifacts = []
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError("reproducibility_artifact_missing")
        artifacts.append(
            {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    return {
        "schema_version": "repro_bundle_v1",
        "commands": [
            "python -m services.offline_acceptance",
            "python -m services.engineering_status",
        ],
        "artifacts": artifacts,
        "negative_results_preserved": True,
        "model_free": True,
        "downloads_attempted": 0,
        "paid_calls": 0,
        "clinical_release": "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        "real_patient_release_authorized": False,
    }
