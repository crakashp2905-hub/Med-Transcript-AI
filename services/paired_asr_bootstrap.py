"""Paired consultation-cluster bootstrap for frozen clean/noisy ASR reports."""

import argparse
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path

from services.api.ingest import file_sha256
from services.detailed_benchmark import fast_score


BOOTSTRAP_VERSION = "paired_foreground_condition_delta_v1"
DEFAULT_ITERATIONS = 10000
DEFAULT_SEED = 20261112


def _percentile(sorted_values, probability):
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def paired_bootstrap(rows, iterations=DEFAULT_ITERATIONS, seed=DEFAULT_SEED):
    if type(iterations) is not int or iterations < 1000:
        raise ValueError("at_least_1000_bootstrap_iterations_required")
    if type(seed) is not int:
        raise ValueError("integer_bootstrap_seed_required")
    pairs = defaultdict(dict)
    for row in rows:
        group = row.get("foreground_id")
        condition = row.get("condition")
        if (
            not isinstance(group, str)
            or not group
            or condition not in ("clean", "distracted")
            or condition in pairs[group]
            or type(row.get("reference_words")) is not int
            or row["reference_words"] <= 0
            or type(row.get("normalized_edits")) is not int
            or row["normalized_edits"] < 0
            or type(row.get("failed")) is not bool
        ):
            raise ValueError("invalid_paired_bootstrap_case")
        if row["failed"] and row["normalized_edits"] != row["reference_words"]:
            raise ValueError("failed_case_must_retain_full_reference_deletions")
        pairs[group][condition] = {
            "group_id": row.get("id"),
            "failed": row["failed"],
            "reference_words": row["reference_words"],
            "normalized_edits": row["normalized_edits"],
        }
    if not pairs or any(
        set(pair) != {"clean", "distracted"} for pair in pairs.values()
    ):
        raise ValueError("complete_clean_distracted_pairs_required")
    for pair in pairs.values():
        clean = pair["clean"]
        distracted = pair["distracted"]
        if clean["reference_words"] != distracted["reference_words"]:
            raise ValueError("paired_reference_denominator_mismatch")

    group_ids = sorted(pairs)
    rng = random.Random(seed)
    differences = []
    for _ in range(iterations):
        selected = rng.choices(group_ids, k=len(group_ids))
        clean_words = sum(
            pairs[group]["clean"]["reference_words"] for group in selected
        )
        distracted_words = sum(
            pairs[group]["distracted"]["reference_words"] for group in selected
        )
        clean_edits = sum(
            pairs[group]["clean"]["normalized_edits"] for group in selected
        )
        distracted_edits = sum(
            pairs[group]["distracted"]["normalized_edits"] for group in selected
        )
        differences.append(
            distracted_edits / distracted_words - clean_edits / clean_words
        )
    differences.sort()
    flattened = [
        {
            "foreground_id": group,
            "clean": pairs[group]["clean"],
            "distracted": pairs[group]["distracted"],
        }
        for group in group_ids
    ]
    clean_words = sum(pair["clean"]["reference_words"] for pair in flattened)
    distracted_words = sum(pair["distracted"]["reference_words"] for pair in flattened)
    clean_edits = sum(pair["clean"]["normalized_edits"] for pair in flattened)
    distracted_edits = sum(pair["distracted"]["normalized_edits"] for pair in flattened)
    failed_pairs = sum(
        pair["clean"]["failed"] or pair["distracted"]["failed"] for pair in flattened
    )
    return {
        "metric_version": BOOTSTRAP_VERSION,
        "method": "resample_foreground_ids_with_both_conditions_intact",
        "estimand": "distracted_micro_WER_minus_clean_micro_WER",
        "confidence_level": 0.95,
        "interval_method": "percentile",
        "iterations": iterations,
        "seed": seed,
        "estimate": distracted_edits / distracted_words - clean_edits / clean_words,
        "low": _percentile(differences, 0.025),
        "high": _percentile(differences, 0.975),
        "quantile_method": "linear_interpolation_type_7",
        "paired_foregrounds": len(group_ids),
        "failed_pairs_included": failed_pairs,
        "failed_pairs_excluded": 0,
        "source_pairs": flattened,
        "limitations": [
            "Convenience-sampled development foregrounds are not an independent clinical acceptance sample.",
            "The interval describes between-foreground resampling variability only; it is not a clinical-validity claim.",
        ],
    }


def run(
    manifest_path,
    report_paths,
    output_path,
    iterations=DEFAULT_ITERATIONS,
    seed=DEFAULT_SEED,
):
    manifest_path = Path(manifest_path).resolve()
    output_path = Path(output_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_hash = file_sha256(manifest_path)
    lock_path = manifest_path.parent / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("manifest_sha256") != manifest_hash:
        raise ValueError("paired_bootstrap_manifest_lock_mismatch")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("paired_bootstrap_manifest_cases_required")
    truth = {case.get("group_id"): case for case in cases}
    if None in truth or len(truth) != len(cases):
        raise ValueError("paired_bootstrap_manifest_ids_invalid")

    candidates = []
    for report_path in sorted(map(Path, report_paths), key=lambda path: path.name):
        report_path = report_path.resolve()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            report.get("complete") is not True
            or report.get("manifest_sha256") != manifest_hash
            or report.get("mode") != "fixed"
        ):
            raise ValueError("paired_bootstrap_requires_complete_fixed_source_reports")
        rows = report.get("cases")
        by_id = {row.get("id"): row for row in rows or []}
        if len(by_id) != len(rows or []) or set(by_id) != set(truth):
            raise ValueError("paired_bootstrap_source_case_coverage_mismatch")
        validated_rows = []
        for case_id, row in by_id.items():
            case = truth[case_id]
            reference = " ".join(
                re.sub(r"<[^>]+>", "", turn["reference"])
                for turn in case["reference_turns"]
            )
            if (
                row.get("foreground_id") != case["foreground_id"]
                or row.get("condition") != case["condition"]
                or row.get("input_sha256") != case["audio_sha256"]
                or row.get("reference") != reference
                or row.get("input_coverage_complete") is not True
            ):
                raise ValueError("paired_bootstrap_source_provenance_mismatch")
            expected = fast_score(
                reference, "" if row.get("failed") else row.get("hypothesis", "")
            )
            if any(row.get(key) != value for key, value in expected.items()):
                raise ValueError("paired_bootstrap_score_reconciliation_failed")
            validated_rows.append(
                {
                    "id": case_id,
                    "foreground_id": case["foreground_id"],
                    "condition": case["condition"],
                    "failed": row["failed"],
                    "reference_words": row["reference_words"],
                    "normalized_edits": row["normalized_edits"],
                }
            )
        candidates.append(
            {
                "candidate_id": report["candidate_id"],
                "source_report": (
                    report_path.relative_to(Path.cwd().resolve()).as_posix()
                    if report_path.is_relative_to(Path.cwd().resolve())
                    else report_path.name
                ),
                "source_report_sha256": file_sha256(report_path),
                "runtime": report.get("runtime"),
                "paired_bootstrap": paired_bootstrap(validated_rows, iterations, seed),
            }
        )
    if not candidates:
        raise ValueError("paired_bootstrap_candidate_reports_required")
    result = {
        "schema_version": "paired_asr_bootstrap_report_v1",
        "scope": "retrospective_development_only",
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": manifest_hash,
        "analysis_source": "services/paired_asr_bootstrap.py",
        "analysis_source_sha256": file_sha256(Path(__file__)),
        "maximum_normalized_wer": 0.05,
        "primary_wer_modified": False,
        "candidates": candidates,
        "clinical_acceptance": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--reports", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    result = run(args.manifest, args.reports, args.out, args.iterations, args.seed)
    print(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "candidates": len(result["candidates"]),
                "paired_foregrounds": result["candidates"][0]["paired_bootstrap"][
                    "paired_foregrounds"
                ],
                "output": args.out,
            },
            separators=(",", ":"),
        )
    )
