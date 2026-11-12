"""Canonical source-of-truth dataset and metric hash ledger."""

import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def build(root="."):
    root = Path(root).resolve()
    datasets = []
    for manifest_path in sorted((root / "evaluation/datasets").glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        datasets.append(
            {
                "dataset_id": manifest["dataset_id"],
                "manifest": manifest_path.relative_to(root).as_posix(),
                "manifest_sha256": hashlib.sha256(
                    manifest_path.read_bytes()
                ).hexdigest(),
                "license_id": manifest.get("license_id"),
                "data_class": manifest.get("data_class"),
                "source_revision": manifest.get("source_revision"),
                "protocol_sha256": manifest.get("protocol_sha256"),
                "split_role": manifest.get("split_role"),
                "grouping": "group_id from consultation identifier; paired conditions are dependent",
                "background_donor_identity": manifest.get(
                    "background_donor_identity", "not_applicable"
                ),
                "transformation": manifest.get("changes"),
                "sources": len(manifest.get("sources", [])),
                "limitations": manifest.get("limitations", []),
            }
        )
    return {
        "schema_version": "dataset_ledger_v1",
        "datasets": datasets,
        "paired_clean_distracted_independence": "not_claimed",
        "clinical_acceptance": False,
    }


def metric_hashes(report):
    samples = report.get("samples", [])
    references = [
        {"sample_id": s.get("sample_id"), "reference": s.get("reference")}
        for s in samples
    ]
    hypotheses = [
        {"sample_id": s.get("sample_id"), "hypothesis": s.get("hypothesis")}
        for s in samples
    ]
    return {
        "reference_sha256": digest(references),
        "hypothesis_sha256": digest(hypotheses),
        "sample_count": len(samples),
    }
