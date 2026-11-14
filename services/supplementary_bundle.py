"""Build sample-level pseudonymous ASR supplement from frozen reports."""

import argparse
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path


def _sample_result(sample, sample_number, group_number, role):
    status = sample.get("status")
    words = sample.get("reference_words")
    edits = sample.get("normalized_edits")
    if (
        status not in {"completed", "failed"}
        or type(words) is not int
        or words < 0
        or type(edits) is not int
        or edits < 0
    ):
        raise ValueError("invalid_frozen_sample_result")
    failed = status == "failed"
    if failed and edits != words:
        raise ValueError("failed_sample_must_count_full_reference_as_deletions")
    return {
        "sample_ref": f"sample-{sample_number:04d}",
        "consultation_cluster": f"consultation-{group_number:02d}",
        "speaker_role": role,
        "candidate_id": sample["candidate_id"],
        "status": status,
        "normalized_edits": edits,
        "reference_words": words,
        "failed_sample": failed,
        "failure_code": sample.get("error_code") if failed else None,
    }


def build(root="."):
    root = Path(root).resolve()
    manifest_path = root / "evaluation/datasets/primock57-expanded-v1/manifest.json"
    lock_path = root / "evaluation/datasets/primock57-expanded-v1/lock.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if lock.get("manifest_sha256") != manifest_sha:
        raise ValueError("supplement_manifest_lock_mismatch")
    if lock.get("failure_policy") != "empty_hypothesis_full_reference_deletions":
        raise ValueError("unsupported_failure_policy")
    ledger = json.loads(
        (root / "evaluation/expanded-ledger.json").read_text(encoding="utf-8")
    )
    samples = manifest.get("samples", [])
    sample_ids = [row.get("sample_id") for row in samples]
    if not samples or len(set(sample_ids)) != len(sample_ids):
        raise ValueError("invalid_supplement_manifest_samples")
    groups = {}
    for row in samples:
        group = row.get("group_id")
        if not isinstance(group, str) or not group:
            raise ValueError("invalid_supplement_manifest_group")
        groups.setdefault(group, len(groups) + 1)
    sample_numbers = {sample_id: i + 1 for i, sample_id in enumerate(sample_ids)}
    result_rows = []
    sources = []
    candidate_ids = set()
    for candidate in ledger["candidates"]:
        if candidate.get("status") != "completed":
            continue
        candidate_id = candidate["candidate_id"]
        candidate_ids.add(candidate_id)
        path = candidate.get("report")
        report_path = (root / path).resolve()
        if not report_path.is_relative_to(root) or not report_path.is_file():
            raise ValueError("supplement_source_report_missing_or_outside_root")
        raw = report_path.read_bytes()
        report = json.loads(raw)
        if report.get("manifest_sha256") != manifest_sha:
            raise ValueError("supplement_source_report_manifest_mismatch")
        by_id = {
            sample.get("sample_id"): sample for sample in report.get("samples", [])
        }
        if set(by_id) != set(sample_ids) or len(by_id) != len(sample_ids):
            raise ValueError("supplement_sample_coverage_mismatch")
        sources.append(
            {
                "candidate_id": candidate_id,
                "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        for source_sample in samples:
            sample_id = source_sample["sample_id"]
            scored = {**by_id[sample_id], "candidate_id": candidate_id}
            result_rows.append(
                _sample_result(
                    scored,
                    sample_numbers[sample_id],
                    groups[source_sample["group_id"]],
                    source_sample.get("speaker_role", "unknown"),
                )
            )
    if not candidate_ids or len(sources) != len(candidate_ids):
        raise ValueError("supplement_completed_candidate_reports_missing")
    failed_count = sum(row["failed_sample"] for row in result_rows)
    csv_stream = io.StringIO(newline="")
    columns = list(result_rows[0])
    writer = csv.DictWriter(csv_stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(result_rows)
    return {
        "schema_version": "sample_level_supplement_v1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "dataset": {
            "dataset_id": manifest["dataset_id"],
            "manifest": "evaluation/datasets/primock57-expanded-v1/manifest.json",
            "manifest_sha256": manifest_sha,
            "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
            "license": lock.get("dataset_license"),
            "sample_count": len(samples),
            "consultation_groups": len(groups),
        },
        "source_reports": sources,
        "failure_policy": lock["failure_policy"],
        "failure_policy_note": "Any failed hypothesis is scored as a full-reference deletion. A failed row with a different edit count is rejected.",
        "sample_results": result_rows,
        "sample_results_csv": csv_stream.getvalue(),
        "failure_count": failed_count,
        "error_taxonomy": {
            "word_level": ["insertion", "substitution", "deletion"],
            "clinical_critical_categories": [
                "medication_or_dose",
                "allergy",
                "negation",
                "omission",
                "speaker_attribution",
                "timestamp_alignment",
            ],
            "clinical_category_labels_available": False,
            "note": "Clinical categories are future independent-adjudication targets; this supplement contains no clinical category scores.",
        },
        "identifiers": {
            "row_id_scheme": "stable ordinal sample and consultation labels",
            "transcript_text_included": False,
            "original_sample_ids_included": False,
            "scope": "Pseudonymous rows for public mock development recordings; not private-patient anonymity evidence.",
        },
        "clinical_release_gate": "not_evaluated",
        "independent_clinical_gold": False,
        "limitations": [
            "These are public mock development samples and are not independent clinical acceptance data.",
            "Pseudonymous row labels omit original sample identifiers and transcript text but do not establish privacy for real patient data.",
            "Clinical-critical categories have no independent labels or scores.",
            "All seven candidates in this supplement are complete local text-only evaluations; gated, resource-blocked, and paid-disabled candidates are excluded and remain unranked in the companion benchmark table.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="evaluation/supplementary/mta-17-05-sample-results-v1.json",
    )
    args = parser.parse_args()
    output = Path(args.output)
    result = build(".")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    output.with_suffix(".csv").write_text(
        result["sample_results_csv"], encoding="utf-8", newline="\n"
    )
    summary = (
        "# Anonymous sample-level ASR supplement\n\n"
        f"Dataset: `{result['dataset']['dataset_id']}`; {result['dataset']['sample_count']} public mock samples; "
        f"{result['dataset']['consultation_groups']} consultation clusters; {len(result['source_reports'])} local candidates.\n\n"
        f"Failure policy: `{result['failure_policy']}`. Failed outputs receive full-reference deletions; observed failed rows: {result['failure_count']}.\n\n"
        "The CSV contains pseudonymous row/consultation IDs, speaker role, candidate, edit count, reference-word denominator, and failure state. It contains no transcript strings or original sample IDs. Clinical-critical taxonomy categories are listed for future adjudication but have no scores. These public mock data do not establish privacy for real patient data or clinical acceptance.\n"
    )
    output.with_suffix(".md").write_text(summary, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "rows": len(result["sample_results"]),
                "status": "written",
            }
        )
    )


if __name__ == "__main__":
    main()
