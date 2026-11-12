"""Failure-inclusive subgroups from frozen ASR reports and turn annotations."""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from services.evaluation import tokens
from services.engineering_status import sha256


def _role(value):
    return "clinician" if value == "doctor" else value or "unknown"


def _overlaps(turn, turns):
    return any(
        _role(other["role"]) != _role(turn["role"])
        and max(turn["start_ms"], other["start_ms"])
        < min(turn["end_ms"], other["end_ms"])
        for other in turns
    )


def _turn_bucket(duration_ms):
    if duration_ms < 1000:
        return "short_lt_1s"
    if duration_ms <= 5000:
        return "medium_1_to_5s"
    return "long_gt_5s"


def _speech_bucket(duration_ms):
    if duration_ms < 30000:
        return "short_lt_30s"
    if duration_ms < 180000:
        return "medium_30_to_180s"
    return "long_gte_180s"


def _new_bucket():
    return {
        "reference_words": 0,
        "substitutions": 0,
        "deletions": 0,
        "unattributed_insertions": 0,
        "annotated_turn_duration_ms": 0,
        "failed_recordings": 0,
        "missing_outputs": 0,
        "_recordings": set(),
        "_consultations": set(),
        "_failed_recordings": set(),
        "_missing_output_recordings": set(),
    }


def _add_turn(
    buckets, label, turn, words, case_id, foreground_id, failed, missing_output
):
    bucket = buckets.setdefault(label, _new_bucket())
    bucket["reference_words"] += words
    bucket["annotated_turn_duration_ms"] += turn["end_ms"] - turn["start_ms"]
    bucket["_recordings"].add(case_id)
    bucket["_consultations"].add(foreground_id)
    if failed:
        bucket["_failed_recordings"].add(case_id)
    if missing_output:
        bucket["_missing_output_recordings"].add(case_id)
    return bucket


def _finish(buckets):
    return {
        label: {
            **{key: value for key, value in bucket.items() if not key.startswith("_")},
            "recordings": len(bucket["_recordings"]),
            "consultation_groups": len(bucket["_consultations"]),
            "normalized_edits": bucket["substitutions"]
            + bucket["deletions"]
            + bucket["unattributed_insertions"],
            "failed_recordings": len(bucket["_failed_recordings"]),
            "missing_outputs": len(bucket["_missing_output_recordings"]),
            "unknown_values_preserved": True,
        }
        for label, bucket in sorted(buckets.items())
    }


def aggregate(manifest, source_reports, error_rows):
    """Aggregate actual annotated conditions/turns without guessing channel roles."""
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest_cases_required")
    truth = {row.get("group_id"): row for row in cases}
    if None in truth or len(truth) != len(cases):
        raise ValueError("invalid_or_duplicate_source_group")

    runs = {}
    turn_index = {}
    for report in source_reports:
        path = report.get("path")
        if (
            not isinstance(path, str)
            or path in runs
            or not isinstance(report.get("candidate_id"), str)
            or not isinstance(report.get("mode"), str)
        ):
            raise ValueError("invalid_or_duplicate_source_report")
        run = {
            "source_report": path,
            "source_report_sha256": report["sha256"],
            "candidate_id": report["candidate_id"],
            "mode": report["mode"],
            "complete": report.get("complete") is True,
            "dimensions": {
                name: {}
                for name in (
                    "recording_condition",
                    "reference_role",
                    "overlap_status",
                    "turn_length",
                    "annotated_turn_duration",
                )
            },
            "unattributed_insertions": 0,
            "missing_output_recordings": 0,
            "failed_recordings": 0,
        }
        runs[path] = run
        report_cases = {row.get("id"): row for row in report.get("cases", [])}
        if len(report_cases) != len(report.get("cases", [])):
            raise ValueError("duplicate_source_report_case")
        for case_id, source in truth.items():
            summary = report_cases.get(case_id)
            missing = summary is None
            failed = missing or (summary.get("failed") is True)
            if missing:
                run["missing_output_recordings"] += 1
            if failed:
                run["failed_recordings"] += 1
            turns = source.get("reference_turns")
            if not isinstance(turns, list):
                raise ValueError("reference_turns_required")
            duration_ms = sum(t["end_ms"] - t["start_ms"] for t in turns)
            speech_label = _speech_bucket(duration_ms)
            condition = source.get("condition") or "unknown"
            group_turns = []
            case_words = 0
            for turn in turns:
                if (
                    type(turn.get("start_ms")) is not int
                    or type(turn.get("end_ms")) is not int
                    or not 0 <= turn["start_ms"] < turn["end_ms"]
                ):
                    raise ValueError("invalid_reference_turn_interval")
                text = re.sub(r"<[^>]+>", "", turn.get("reference", ""))
                words = len(tokens(text))
                case_words += words
                duration = turn["end_ms"] - turn["start_ms"]
                overlap = _overlaps(turn, turns)
                role = _role(turn.get("role"))
                values = {
                    "recording_condition": condition,
                    "reference_role": role,
                    "overlap_status": "overlapping" if overlap else "not_overlapping",
                    "turn_length": _turn_bucket(duration),
                    "annotated_turn_duration": speech_label,
                }
                group_turns.append(
                    {
                        "start_ms": turn["start_ms"],
                        "end_ms": turn["end_ms"],
                        "role": role,
                        "values": values,
                    }
                )
                for dimension, value in values.items():
                    bucket = _add_turn(
                        run["dimensions"][dimension],
                        value,
                        turn,
                        words,
                        case_id,
                        source.get("foreground_id") or case_id,
                        failed,
                        missing,
                    )
                    if missing:
                        bucket["deletions"] += words
            turn_index[(path, case_id)] = group_turns
            if not missing and summary.get("reference_words") != case_words:
                raise ValueError("source_report_reference_denominator_mismatch")

    operation_counts = defaultdict(Counter)
    report_case_ids = {
        path: {row.get("id") for row in report.get("cases", [])}
        for path, report in ((item["path"], item) for item in source_reports)
    }

    for event in error_rows:
        path, case_id = event.get("report"), event.get("case")
        if path not in runs or case_id not in truth:
            raise ValueError("error_event_outside_frozen_run")
        run = runs[path]
        if case_id not in report_case_ids[path]:
            raise ValueError("edit_event_for_missing_output_case")
        if (
            event.get("candidate") != run["candidate_id"]
            or event.get("mode") != run["mode"]
        ):
            raise ValueError("error_event_run_identity_mismatch")
        operation = event.get("operation")
        operation_counts[(path, case_id)][operation] += 1
        if operation == "insertion":
            run["unattributed_insertions"] += 1
            condition = truth[case_id].get("condition") or "unknown"
            run["dimensions"]["recording_condition"].setdefault(
                condition, _new_bucket()
            )["unattributed_insertions"] += 1
            continue
        start, end = event.get("start_ms"), event.get("end_ms")
        role = event.get("reference_role")
        if start is None or end is None or role is None:
            raise ValueError("reference_edit_missing_source_interval")
        matching = [
            turn
            for turn in turn_index[(path, case_id)]
            if turn["start_ms"] == int(start)
            and turn["end_ms"] == int(end)
            and turn["role"] == role
        ]
        if not matching:
            raise ValueError("edit_does_not_resolve_to_reference_turn")
        metric = {
            "substitution": "substitutions",
            "deletion": "deletions",
        }.get(operation)
        if metric is None:
            raise ValueError("unknown_error_operation")
        for dimension, value in matching[0]["values"].items():
            run["dimensions"][dimension][value][metric] += 1

    for report in source_reports:
        for case in report.get("cases", []):
            counts = operation_counts[(report["path"], case["id"])]
            total = sum(
                counts[operation]
                for operation in ("insertion", "deletion", "substitution")
            )
            if total != case.get("normalized_edits"):
                raise ValueError("subgroup_edit_count_mismatch")

    results = []
    for run in runs.values():
        results.append(
            {
                **{key: value for key, value in run.items() if key != "dimensions"},
                "dimensions": {
                    name: _finish(buckets)
                    for name, buckets in run["dimensions"].items()
                },
                "channel_mapping": {
                    "status": "unknown_not_measured",
                    "reason": "source_audio_channel_metadata_unavailable",
                },
            }
        )
    return {
        "schema_version": "asr_subgroup_diagnostics_v1",
        "dataset_id": manifest.get("dataset_id"),
        "scope": "saved_development_hypotheses",
        "runs": results,
        "limitations": [
            "Subgroup strata use source reference turn annotations and lexical edits, not predicted diarization.",
            "Annotated turn duration is a metadata proxy, not measured active speech time; overlap can be counted more than once.",
            "Channel mapping remains unknown because audio channel metadata is unavailable.",
            "Missing case outputs are counted as full-reference deletions; insertion ownership is left unattributed.",
        ],
        "clinical_acceptance": False,
    }


def run(manifest_path, receipt_path, error_csv_path, output_path):
    manifest_path, receipt_path, error_csv_path = map(
        Path, (manifest_path, receipt_path, error_csv_path)
    )
    manifest = json.loads(manifest_path.read_bytes())
    receipt = json.loads(receipt_path.read_bytes())
    if receipt.get("manifest_sha256") != sha256(manifest_path):
        raise ValueError("subgroup_manifest_digest_mismatch")
    if receipt.get("csv_sha256") != sha256(error_csv_path):
        raise ValueError("subgroup_error_csv_digest_mismatch")
    expected = {row["path"]: row["sha256"] for row in receipt["reports"]}
    source_reports = []
    for relative, digest in expected.items():
        path = Path(relative)
        if sha256(path) != digest:
            raise ValueError("subgroup_source_report_digest_mismatch")
        source_reports.append(json.loads(path.read_bytes()))
        source_reports[-1]["path"] = relative
        source_reports[-1]["sha256"] = digest
    with error_csv_path.open(encoding="utf-8", newline="") as stream:
        result = aggregate(manifest, source_reports, csv.DictReader(stream))
    result.update(
        manifest_sha256=sha256(manifest_path),
        taxonomy_receipt_sha256=sha256(receipt_path),
        error_csv_sha256=sha256(error_csv_path),
        source_code_sha256=sha256(Path(__file__)),
    )
    with Path(output_path).open("x", encoding="utf-8", newline="\n") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--errors", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run(args.manifest, args.receipt, args.errors, args.out)
    print(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "runs": len(result["runs"]),
                "manifest_sha256": result["manifest_sha256"],
                "error_csv_sha256": result["error_csv_sha256"],
                "output": args.out,
            },
            separators=(",", ":"),
        )
    )
