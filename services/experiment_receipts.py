"""Validate hypothesis-bound experiment receipts and their local evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTCOMES = {"success", "null_result", "harmful_regression", "not_run"}


def validate_receipts(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "experiment_receipts_v1":
        raise ValueError("invalid_experiment_receipt_schema")
    experiments = receipt.get("experiments")
    if not isinstance(experiments, list) or not experiments:
        raise ValueError("experiment_receipts_required")
    ids = set()
    for experiment in experiments:
        experiment_id = experiment.get("experiment_id")
        if (
            not isinstance(experiment_id, str)
            or not experiment_id
            or experiment_id in ids
        ):
            raise ValueError("experiment_id_missing_or_duplicate")
        ids.add(experiment_id)
        if (
            not isinstance(experiment.get("hypothesis"), str)
            or not experiment["hypothesis"].strip()
        ):
            raise ValueError(f"{experiment_id}: hypothesis_required")
        if experiment.get("outcome") not in OUTCOMES:
            raise ValueError(f"{experiment_id}: invalid_outcome")
        if not isinstance(experiment.get("result"), dict):
            raise ValueError(f"{experiment_id}: result_required")
        for evidence in experiment.get("evidence", []):
            relative = evidence.get("path")
            if not isinstance(relative, str) or Path(relative).is_absolute():
                raise ValueError(f"{experiment_id}: invalid_evidence_path")
            resolved = (ROOT / relative).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.is_file():
                raise ValueError(f"{experiment_id}: evidence_missing")
            if hashlib.sha256(resolved.read_bytes()).hexdigest() != evidence.get(
                "sha256"
            ):
                raise ValueError(f"{experiment_id}: evidence_hash_mismatch")
    return {
        "experiment_count": len(experiments),
        "outcomes": [e["outcome"] for e in experiments],
    }
