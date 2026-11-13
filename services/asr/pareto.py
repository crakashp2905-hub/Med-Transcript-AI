"""Post-hoc ASR latency/accuracy Pareto report from matched frozen runs."""

import argparse
import hashlib
import importlib.metadata
import json
import math
from itertools import combinations
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from services.asr.rover import rover_vote
from services.evaluation import PROJECT_MAX_NORMALIZED_WER, tokens, wer_gate


def _p95(values):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)] if ordered else None


def _p50(values):
    """Return the median without rounding away half-sample runtimes."""
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _score(reference, hypothesis):
    reference_words = tokens(reference)
    hypothesis_words = tokens(hypothesis)
    return len(reference_words), Levenshtein.distance(reference_words, hypothesis_words)


def _case_duration(case):
    chunks = case.get("chunks", [])
    if not chunks:
        raise ValueError("case_chunk_duration_required")
    return max(float(chunk["end_ms"]) for chunk in chunks) / 1000


def _validate_runs(paths, suite_path):
    reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    if len(reports) < 2:
        raise ValueError("at_least_two_matched_engine_reports_required")
    suite_file = Path(suite_path)
    suite = json.loads(suite_file.read_text(encoding="utf-8"))
    suite_digest = hashlib.sha256(suite_file.read_bytes()).hexdigest()
    first = reports[0]
    if first.get("suite_sha256") != suite_digest:
        raise ValueError("frozen_suite_digest_mismatch")
    candidates = {}
    for report in reports:
        candidate = report.get("candidate_id")
        if (
            report.get("schema_version") != "detailed_full_asr_v1"
            or report.get("complete") is not True
            or report.get("mode") != "fixed"
            or report.get("suite_sha256") != suite_digest
            or report.get("manifest_sha256") != first.get("manifest_sha256")
            or candidate in candidates
        ):
            raise ValueError("unique_matched_fixed_reports_required")
        candidates[candidate] = {row["id"]: row for row in report["cases"]}
    case_ids = set(next(iter(candidates.values())))
    if any(set(rows) != case_ids for rows in candidates.values()):
        raise ValueError("matched_case_sets_required")
    base = next(iter(candidates.values()))
    for case_id in case_ids:
        source = base[case_id]
        for rows in candidates.values():
            candidate = rows[case_id]
            if (
                candidate.get("input_sha256") != source.get("input_sha256")
                or candidate.get("reference") != source.get("reference")
                or candidate.get("foreground_id") != source.get("foreground_id")
                or candidate.get("condition") != source.get("condition")
                or candidate.get("input_coverage_complete") is not True
            ):
                raise ValueError("matched_audio_reference_coverage_required")
    jobs = {row["candidate_id"]: row for row in suite.get("jobs", [])}
    return reports, candidates, jobs, suite_digest, case_ids


def _single_engine(report, rows):
    cases = list(rows.values())
    reference_words = sum(row["reference_words"] for row in cases)
    edits = sum(row["normalized_edits"] for row in cases)
    failures = sum(bool(row["failed"]) for row in cases)
    latency = [float(row["wall_seconds"]) for row in cases]
    rtfs = [elapsed / _case_duration(row) for elapsed, row in zip(latency, cases)]
    model_load_seconds = report.get("model_load_seconds")
    resource = report.get("resource_measurement") or {}
    return {
        "candidate_id": report["candidate_id"],
        "sample_count": len(cases),
        "failed_samples": failures,
        "reference_words": reference_words,
        "normalized_edits": edits,
        "normalized_wer": edits / reference_words if reference_words else None,
        "wer_gate": wer_gate(
            {
                "reference_words": reference_words,
                "normalized_edits": edits,
                "failed_samples": failures,
            },
            PROJECT_MAX_NORMALIZED_WER,
        ),
        "model_load_seconds": model_load_seconds,
        "cpu_seconds": resource.get("cpu_seconds"),
        "maximum_process_memory_bytes": resource.get("peak_resident_bytes"),
        "measured_local_inference_cost_usd": 0.0,
        "case_wall_seconds_sum": sum(latency),
        "case_wall_seconds_p50": _p50(latency),
        "case_wall_seconds_p95": _p95(latency),
        "real_time_factor_p95": _p95(rtfs),
    }


def _pair_engine(
    left_id, right_id, left, right, case_ids, left_resources, right_resources
):
    rows, latencies, rtfs = [], [], []
    for case_id in sorted(case_ids):
        a, b = left[case_id], right[case_id]
        failed = bool(a["failed"] or b["failed"])
        vote = rover_vote(
            [
                {
                    "backend_id": left_id,
                    "text": "" if a["failed"] else a["hypothesis"],
                },
                {
                    "backend_id": right_id,
                    "text": "" if b["failed"] else b["hypothesis"],
                },
            ],
            left_id,
        )
        words, edits = _score(a["reference"], vote["text"])
        rows.append(
            {
                "case_id": case_id,
                "reference_words": words,
                "normalized_edits": edits,
                "failed": failed,
            }
        )
        duration = _case_duration(a)
        latencies.append(float(a["wall_seconds"]) + float(b["wall_seconds"]))
        rtfs.append(latencies[-1] / duration)
    reference_words = sum(row["reference_words"] for row in rows)
    edits = sum(row["normalized_edits"] for row in rows)
    failures = sum(row["failed"] for row in rows)
    return {
        "candidate_ids": [left_id, right_id],
        "sample_count": len(rows),
        "failed_samples": failures,
        "reference_words": reference_words,
        "normalized_edits": edits,
        "normalized_wer": edits / reference_words if reference_words else None,
        "wer_gate": wer_gate(
            {
                "reference_words": reference_words,
                "normalized_edits": edits,
                "failed_samples": failures,
            },
            PROJECT_MAX_NORMALIZED_WER,
        ),
        "serial_case_wall_seconds_sum": sum(latencies),
        "serial_case_wall_seconds_p50": _p50(latencies),
        "serial_case_wall_seconds_p95": _p95(latencies),
        "serial_real_time_factor_p95": _p95(rtfs),
        "cpu_seconds": sum(
            value
            for value in (
                (left_resources.get("resource_measurement") or {}).get("cpu_seconds"),
                (right_resources.get("resource_measurement") or {}).get("cpu_seconds"),
            )
            if isinstance(value, (int, float))
        )
        if all(
            isinstance(
                (report.get("resource_measurement") or {}).get("cpu_seconds"),
                (int, float),
            )
            for report in (left_resources, right_resources)
        )
        else None,
        "maximum_process_memory_bytes": max(
            (
                value
                for value in (
                    (left_resources.get("resource_measurement") or {}).get(
                        "peak_resident_bytes"
                    ),
                    (right_resources.get("resource_measurement") or {}).get(
                        "peak_resident_bytes"
                    ),
                )
                if isinstance(value, (int, float))
            ),
            default=None,
        ),
        "measured_local_inference_cost_usd": 0.0,
        "latency_assumption": "sequential full-decode wall-time sum; no targeted crop savings assumed",
    }


def run(report_paths, suite_path, output_path):
    reports, candidates, jobs, suite_digest, case_ids = _validate_runs(
        report_paths, suite_path
    )
    singles = {
        report["candidate_id"]: _single_engine(
            report, candidates[report["candidate_id"]]
        )
        for report in reports
    }
    pairs = [
        _pair_engine(
            a,
            b,
            candidates[a],
            candidates[b],
            case_ids,
            next(report for report in reports if report["candidate_id"] == a),
            next(report for report in reports if report["candidate_id"] == b),
        )
        for a, b in combinations(sorted(candidates), 2)
    ]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "asr_compute_accuracy_pareto_v1",
        "manifest_sha256": reports[0]["manifest_sha256"],
        "suite_sha256": suite_digest,
        "source_reports": [
            {
                "candidate_id": report["candidate_id"],
                "path": str(path),
                "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            }
            for report, path in zip(reports, report_paths)
        ],
        "model_configurations": {
            candidate: jobs.get(candidate) for candidate in sorted(candidates)
        },
        "source_code_sha256": {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in (
                "services/asr/pareto.py",
                "services/asr/rover.py",
                "services/evaluation.py",
            )
        },
        "runtime_dependency": {
            "rapidfuzz_version": importlib.metadata.version("rapidfuzz")
        },
        "single_engine": list(singles.values()),
        "two_engine_rover": pairs,
        "targeted_fallback": {
            "status": "not_evaluated",
            "reason": "No predeclared risk-selected paired fallback inference report exists.",
        },
        "resource_limits": {
            "asr_peak_memory_bytes": "reported_per_engine_when_source_receipt_contains_measurement",
            "cpu_seconds": "reported_per_engine_when_source_receipt_contains_measurement",
            "wall_latency": "measured_case_wall_time_from_frozen_reports",
        },
        "admission_maximum_normalized_wer": PROJECT_MAX_NORMALIZED_WER,
        "clinical_acceptance": False,
        "limitations": [
            "Source runs are saved development measurements, not a fresh concurrent benchmark.",
            "Pair latency is the sum of serialized engine wall times; memory is not inferred.",
            "No candidate meets the frozen WER gate and failures remain admission failures.",
        ],
    }
    with output.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(payload, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", nargs="+", required=True)
    parser.add_argument("--suite", default="evaluation/detailed-suite-v2.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = run(args.reports, args.suite, args.out)
    print(
        json.dumps(
            {"single": report["single_engine"], "pairs": report["two_engine_rover"]},
            indent=2,
        )
    )
