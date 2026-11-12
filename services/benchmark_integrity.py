"""Recompute saved full-consultation scores without inference or reference changes."""

import argparse
import hashlib
import json
from pathlib import Path
from services.detailed_benchmark import fast_score
from services.engineering_status import sha256


def replay(report, manifest):
    truth = {c["group_id"]: c for c in manifest["cases"]}
    seen = set()
    import re

    for row in report["cases"]:
        if row["id"] not in truth or row["id"] in seen:
            raise ValueError("unknown_or_duplicate_case")
        seen.add(row["id"])
        source = truth[row["id"]]
        reference = " ".join(
            re.sub(r"<[^>]+>", "", t["reference"]) for t in source["reference_turns"]
        )
        if (
            reference != row["reference"]
            or source["audio_sha256"] != row["input_sha256"]
        ):
            raise ValueError("source_reference_or_audio_identity_changed")
        measured = fast_score(reference, row["hypothesis"])
        if any(
            not isinstance(row.get(key), int)
            or isinstance(row[key], bool)
            or row[key] < 0
            for key in measured
        ):
            raise ValueError("invalid_benchmark_arithmetic_type")
        if any(row[key] != value for key, value in measured.items()):
            raise ValueError("saved_score_mismatch")
        if row["failed"] and row["hypothesis"] != "":
            raise ValueError("failure_denominator_policy_violation")
        if not row["input_coverage_complete"]:
            raise ValueError("completed_case_has_incomplete_coverage")
    if report["complete"] and seen != set(truth):
        raise ValueError("complete_report_missing_predeclared_cases")
    return {
        "completed_cases": len(seen),
        "predeclared_cases": len(truth),
        "complete": report["complete"],
        "reference_words": sum(row["reference_words"] for row in report["cases"]),
        "failed_cases": sum(row["failed"] for row in report["cases"]),
        "per_case_text_sha256": [
            {
                "id": r["id"],
                "reference": __import__("hashlib")
                .sha256(r["reference"].encode())
                .hexdigest(),
                "hypothesis": __import__("hashlib")
                .sha256(r["hypothesis"].encode())
                .hexdigest(),
            }
            for r in report["cases"]
        ],
    }


def audit(root="."):
    root = Path(root)
    manifest_path = root / "evaluation/datasets/meddistract-detailed-v1/manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest_hash = hashlib.sha256(manifest_raw).hexdigest()
    manifest = json.loads(manifest_raw)
    reports = []
    for folder in (
        "meddistract-detailed-v1",
        "meddistract-detailed-v2",
        "meddistract-recovery-v3",
    ):
        for path in sorted((root / "evaluation/runs" / folder).glob("*.json")):
            raw = path.read_bytes()
            report_hash = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            if "cases" not in data:
                continue
            measured = replay(data, manifest)
            if sha256(path) != report_hash:
                raise ValueError("report_changed_during_replay")
            reports.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": report_hash,
                    "candidate": data["candidate_id"],
                    "mode": data["mode"],
                    **measured,
                }
            )
    if sha256(manifest_path) != manifest_hash:
        raise ValueError("manifest_changed_during_replay")
    return {
        "schema_version": "saved_benchmark_replay_v1",
        "manifest_sha256": manifest_hash,
        "reports": reports,
        "inference_calls": 0,
        "references_modified": False,
        "maximum_normalized_wer": 0.05,
        "independent_clinical_gold": False,
        "clinical_release": False,
        "real_patient_release_authorized": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with Path(args.out).open("x", encoding="utf-8") as output:
        json.dump(audit(), output, indent=2)
