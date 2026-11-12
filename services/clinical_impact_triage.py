"""Provisional review ordering for lexical ASR errors, not clinical severity."""

from collections import Counter
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from services.api.ingest import file_sha256
from services.review.clinical import MEDICATION, NEGATION, QUANTITY


FREQUENCY = re.compile(
    r"\b(?:once|twice|daily|weekly|monthly|nightly|every|times? a day|"
    r"times? daily|q[0-9]+h)\b",
    re.I,
)
ALLERGY = re.compile(r"allerg", re.I)
CHRONOLOGY = re.compile(
    r"\b(?:today|yesterday|tomorrow|currently|now|before|after|since|"
    r"prior|previously|recently|last|next|then|started|stopped)\b",
    re.I,
)
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")

CATEGORY_TIERS = {
    "identity_or_speaker_attribution": 1,
    "medication_name": 1,
    "dose_or_strength_value": 1,
    "allergy": 1,
    "negation_or_assertion": 1,
    "dosing_frequency": 2,
    "number_or_unit": 2,
    "chronology": 2,
    "other_lexical_error": 3,
}


def classify_edit(row):
    """Assign overlapping lexical cues and the highest provisional review tier."""
    if not isinstance(row, dict):
        raise ValueError("error_row_must_be_object")
    reference = row.get("reference_token") or ""
    hypothesis = row.get("hypothesis_token") or ""
    if not isinstance(reference, str) or not isinstance(hypothesis, str):
        raise ValueError("error_tokens_must_be_text")
    text = f"{reference} {hypothesis}".strip()
    categories = []
    if row.get("identity_attribution_error") is True:
        categories.append("identity_or_speaker_attribution")
    if MEDICATION.search(text):
        categories.append("medication_name")
    if QUANTITY.search(text) or row.get("dose_context") is True:
        categories.append("dose_or_strength_value")
    if NUMBER.search(text) or re.search(r"\b(?:mcg|mg|kg|g|ml|l|units?)\b", text, re.I):
        categories.append("number_or_unit")
    if ALLERGY.search(text):
        categories.append("allergy")
    if NEGATION.search(text):
        categories.append("negation_or_assertion")
    if FREQUENCY.search(text):
        categories.append("dosing_frequency")
    if CHRONOLOGY.search(text):
        categories.append("chronology")
    categories = sorted(
        set(categories), key=lambda category: (CATEGORY_TIERS[category], category)
    )
    if not categories:
        categories = ["other_lexical_error"]
    return {
        **row,
        "provisional_impact_categories": categories,
        "provisional_review_tier": min(CATEGORY_TIERS[name] for name in categories),
        "clinical_severity_validated": False,
    }


def summarize(rows):
    """Summarize rows by cue, operation and annotated reference role."""
    category_counts = Counter()
    operation_counts = Counter()
    role_counts = Counter()
    total = 0
    for source in rows:
        row = classify_edit(source)
        total += 1
        operation_counts[row.get("operation", "unknown")] += 1
        role_counts[row.get("reference_role", "unknown")] += 1
        category_counts.update(row["provisional_impact_categories"])
    return {
        "schema_version": "provisional_clinical_error_triage_summary_v1",
        "status": "unvalidated_review_order",
        "error_rows": total,
        "category_counts_overlap": True,
        "by_priority_tier": {
            str(tier): sorted(
                category for category, value in CATEGORY_TIERS.items() if value == tier
            )
            for tier in (1, 2, 3)
        },
        "category_counts": {
            category: category_counts[category] for category in sorted(CATEGORY_TIERS)
        },
        "operation_counts": dict(sorted(operation_counts.items())),
        "reference_role_counts": dict(sorted(role_counts.items())),
        "identity_attribution": "only explicit independent annotation flags are counted",
        "clinical_harm_labels_available": False,
        "clinical_severity_validated": False,
        "release_authorized": False,
    }


def audit_saved_corpus(root="."):
    """Classify the frozen local error CSV without changing source evidence."""
    root = Path(root).resolve()
    relative = {
        "taxonomy_report": "evaluation/reports/error-taxonomy-v2/report.json",
        "csv_archive": "evaluation/reports/error-taxonomy-v2/all-errors.csv.zip",
        "manifest": "evaluation/datasets/meddistract-detailed-v1/manifest.json",
        "protocol": "evaluation/error-taxonomy-protocol-v2.json",
    }
    paths = {name: root / value for name, value in relative.items()}
    taxonomy = json.loads(paths["taxonomy_report"].read_text(encoding="utf-8"))
    protocol = json.loads(paths["protocol"].read_text(encoding="utf-8"))
    manifest_sha = file_sha256(paths["manifest"])
    archive_sha = file_sha256(paths["csv_archive"])
    if (
        taxonomy.get("manifest_sha256") != manifest_sha
        or protocol.get("manifest_sha256") != manifest_sha
        or taxonomy.get("csv_archive_sha256") != archive_sha
    ):
        raise ValueError("saved_error_corpus_integrity_failure")
    declared_reports = {
        item["path"]: item["sha256"] for item in protocol["source_reports"]
    }
    if {
        item["path"]: item["sha256"] for item in taxonomy["reports"]
    } != declared_reports:
        raise ValueError("saved_error_report_set_mismatch")
    for path, digest in declared_reports.items():
        if file_sha256(root / path) != digest:
            raise ValueError("saved_error_report_hash_mismatch")
    with zipfile.ZipFile(paths["csv_archive"]) as archive:
        info = archive.getinfo("all-errors.csv")
        if info.file_size > 128 * 1024 * 1024:
            raise ValueError("saved_error_csv_size_limit")
        raw_csv = archive.read("all-errors.csv")
    csv_sha = hashlib.sha256(raw_csv).hexdigest()
    if csv_sha != taxonomy.get("csv_sha256"):
        raise ValueError("saved_error_csv_hash_mismatch")
    rows = list(
        csv.DictReader(
            io.TextIOWrapper(io.BytesIO(raw_csv), encoding="utf-8", newline="")
        )
    )
    summary = summarize(rows)
    return {
        "schema_version": "clinical_error_review_triage_receipt_v1",
        "policy": "evaluation/clinical-impact-triage-v1.json",
        "policy_sha256": file_sha256(
            root / "evaluation/clinical-impact-triage-v1.json"
        ),
        "manifest_sha256": manifest_sha,
        "taxonomy_report_sha256": file_sha256(paths["taxonomy_report"]),
        "csv_archive_sha256": archive_sha,
        "csv_sha256": csv_sha,
        "source_report_count": len(declared_reports),
        "source_reports_sha256": declared_reports,
        "inference_calls": 0,
        **{key: value for key, value in summary.items() if key != "schema_version"},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(audit_saved_corpus(args.root), target, ensure_ascii=False, indent=2)
        target.write("\n")


if __name__ == "__main__":
    main()
