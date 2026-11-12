"""Post-hoc ROVER-style confusion-network baseline for frozen ASR reports."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from services.evaluation import tokens


def _align(left, right):
    """C-optimized exact Levenshtein token alignment."""
    aligned = []
    opcodes = Levenshtein.opcodes(left, right)
    for opcode in opcodes:
        tag = opcode.tag
        i1, i2 = opcode.src_start, opcode.src_end
        j1, j2 = opcode.dest_start, opcode.dest_end
        if tag == "equal":
            aligned.extend((i1 + offset, j1 + offset) for offset in range(i2 - i1))
        elif tag == "replace":
            paired = min(i2 - i1, j2 - j1)
            aligned.extend((i1 + offset, j1 + offset) for offset in range(paired))
            aligned.extend((index, None) for index in range(i1 + paired, i2))
            aligned.extend((None, index) for index in range(j1 + paired, j2))
        elif tag == "delete":
            aligned.extend((index, None) for index in range(i1, i2))
        else:
            aligned.extend((None, index) for index in range(j1, j2))
    return aligned


def rover_vote(hypotheses, pivot_backend_id):
    """Build pivot-anchored token columns; ties favor pivot, then gap, then text."""
    if not isinstance(hypotheses, list) or len(hypotheses) < 2:
        raise ValueError("at_least_two_rover_hypotheses_required")
    texts, words = {}, {}
    for row in hypotheses:
        backend_id, text = row.get("backend_id"), row.get("text")
        if (
            not isinstance(backend_id, str)
            or not backend_id
            or backend_id in texts
            or not isinstance(text, str)
        ):
            raise ValueError("unique_text_hypotheses_required")
        texts[backend_id] = text
        words[backend_id] = tokens(text)
    if pivot_backend_id not in words:
        raise ValueError("rover_pivot_backend_missing")

    pivot = words[pivot_backend_id]
    columns = [
        {backend_id: None for backend_id in words} | {pivot_backend_id: token}
        for token in pivot
    ]
    insertions = [
        {backend_id: [] for backend_id in words} for _ in range(len(pivot) + 1)
    ]
    for backend_id, candidate in words.items():
        if backend_id == pivot_backend_id:
            continue
        pivot_cursor = 0
        for pivot_index, candidate_index in _align(pivot, candidate):
            if pivot_index is None:
                insertions[pivot_cursor][backend_id].append(candidate[candidate_index])
            else:
                columns[pivot_index][backend_id] = (
                    candidate[candidate_index] if candidate_index is not None else None
                )
                pivot_cursor = pivot_index + 1

    network = []
    for boundary in range(len(pivot) + 1):
        width = max(
            (len(sequence) for sequence in insertions[boundary].values()), default=0
        )
        for offset in range(width):
            network.append(
                {
                    backend_id: (sequence[offset] if offset < len(sequence) else None)
                    for backend_id, sequence in insertions[boundary].items()
                }
            )
        if boundary < len(pivot):
            network.append(columns[boundary])

    voted, vote_rows = [], []
    for column_index, column in enumerate(network):
        counts = {}
        for token in column.values():
            counts[token] = counts.get(token, 0) + 1
        maximum = max(counts.values())
        tied = [token for token, count in counts.items() if count == maximum]
        pivot_token = column.get(pivot_backend_id)
        if pivot_token in tied:
            winner, tie_break = pivot_token, "pivot"
        elif None in tied:
            winner, tie_break = None, "gap"
        else:
            winner, tie_break = min(tied), "lexical"
        if winner is not None:
            voted.append(winner)
        vote_rows.append(
            {
                "column_index": column_index,
                "votes": column,
                "winner": winner,
                "tie_break": tie_break if len(tied) > 1 else None,
            }
        )
    return {
        "text": " ".join(voted),
        "tokens": voted,
        "confusion_network": vote_rows,
        "pivot_backend_id": pivot_backend_id,
        "candidate_selection": "majority_token_vote",
        "confidence": None,
        "clinical_truth_asserted": False,
    }


def _score(reference, hypothesis):
    normalized_reference = tokens(reference)
    normalized_hypothesis = tokens(hypothesis)
    raw_reference = tokens(reference, normalized=False)
    raw_hypothesis = tokens(hypothesis, normalized=False)
    if (
        max(
            len(normalized_reference),
            len(normalized_hypothesis),
            len(raw_reference),
            len(raw_hypothesis),
        )
        > 10000
    ):
        raise ValueError("Scoring token limit exceeded")
    return {
        "reference_words": len(normalized_reference),
        "hypothesis_words": len(normalized_hypothesis),
        "normalized_edits": Levenshtein.distance(
            normalized_reference, normalized_hypothesis
        ),
        "raw_reference_words": len(raw_reference),
        "raw_edits": Levenshtein.distance(raw_reference, raw_hypothesis),
    }


def _summary(rows):
    reference_words = sum(row["reference_words"] for row in rows)
    edits = sum(row["normalized_edits"] for row in rows)
    return {
        "sample_count": len(rows),
        "failed_samples": sum(row["candidate_failed"] for row in rows),
        "reference_words": reference_words,
        "normalized_edits": edits,
        "normalized_wer": edits / reference_words if reference_words else None,
    }


def run(
    report_paths,
    output_path,
    pivot_backend_id,
    suite_path="evaluation/detailed-suite-v2.json",
):
    reports = [
        json.loads(Path(path).read_text(encoding="utf-8")) for path in report_paths
    ]
    if len(reports) < 2:
        raise ValueError("at_least_two_frozen_reports_required")
    first = reports[0]
    for report in reports:
        if (
            report.get("schema_version") != "detailed_full_asr_v1"
            or not report.get("complete")
            or report.get("mode") != "fixed"
            or report.get("manifest_sha256") != first.get("manifest_sha256")
            or report.get("suite_sha256") != first.get("suite_sha256")
        ):
            raise ValueError("matched_complete_fixed_reports_required")
    suite_file = Path(suite_path)
    suite = json.loads(suite_file.read_text(encoding="utf-8"))
    suite_sha256 = hashlib.sha256(suite_file.read_bytes()).hexdigest()
    if suite_sha256 != first.get("suite_sha256"):
        raise ValueError("frozen_suite_digest_mismatch")
    suite_jobs = {
        row["candidate_id"]: row
        for row in suite.get("jobs", [])
        if isinstance(row, dict) and isinstance(row.get("candidate_id"), str)
    }
    by_backend = {}
    for report in reports:
        backend_id = report.get("candidate_id")
        if not isinstance(backend_id, str) or backend_id in by_backend:
            raise ValueError("unique_frozen_candidate_reports_required")
        by_backend[backend_id] = {row["id"]: row for row in report.get("cases", [])}
    if pivot_backend_id not in by_backend:
        raise ValueError("rover_pivot_backend_missing")
    case_ids = set(by_backend[pivot_backend_id])
    if any(set(rows) != case_ids for rows in by_backend.values()):
        raise ValueError("paired_case_sets_mismatch")

    rows, source_rows = [], {backend: [] for backend in by_backend}
    for case_id in sorted(case_ids):
        base = by_backend[pivot_backend_id][case_id]
        hypotheses = []
        any_failed = False
        for backend_id, cases in by_backend.items():
            row = cases[case_id]
            if (
                row.get("input_sha256") != base.get("input_sha256")
                or row.get("reference") != base.get("reference")
                or not row.get("input_coverage_complete")
            ):
                raise ValueError("paired_audio_reference_or_coverage_mismatch")
            failed = bool(row.get("failed"))
            any_failed |= failed
            hypotheses.append(
                {
                    "backend_id": backend_id,
                    "text": "" if failed else row.get("hypothesis", ""),
                }
            )
            source_rows[backend_id].append(
                {
                    "reference": row["reference"],
                    "hypothesis": "" if failed else row.get("hypothesis", ""),
                    "failed_samples": int(failed),
                }
            )
        vote = rover_vote(hypotheses, pivot_backend_id)
        scored = _score(base["reference"], vote["text"])
        rows.append(
            {
                "case_id": case_id,
                "foreground_id": base["foreground_id"],
                "condition": base["condition"],
                "input_sha256": base["input_sha256"],
                "candidate_failed": any_failed,
                "reference": base["reference"],
                "hypothesis": vote["text"],
                **scored,
                "vote": vote,
            }
        )

    source_summaries = {}
    for backend_id, source in source_rows.items():
        scored_rows = [
            {
                "reference": item["reference"],
                "hypothesis": item["hypothesis"],
                "candidate_failed": bool(item["failed_samples"]),
                **_score(item["reference"], item["hypothesis"]),
            }
            for item in source
        ]
        source_summaries[backend_id] = _summary(scored_rows)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "rover_matched_development_v1",
        "manifest_sha256": first["manifest_sha256"],
        "suite_sha256": first["suite_sha256"],
        "source_reports": [
            {
                "candidate_id": report["candidate_id"],
                "path": str(path),
                "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            }
            for report, path in zip(reports, report_paths)
        ],
        "model_configurations": {
            report["candidate_id"]: suite_jobs.get(report["candidate_id"])
            for report in reports
        },
        "source_code_sha256": {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in ("services/asr/rover.py", "services/evaluation.py")
        },
        "runtime_dependencies": {"rapidfuzz": importlib.metadata.version("rapidfuzz")},
        "pivot_backend_id": pivot_backend_id,
        "method": "pivot-anchored exact Levenshtein token alignment; majority vote; ties favor pivot, then gap, then lexical order",
        "failure_policy": "all source failures retained in denominators; any failed source marks the paired ROVER sample failed",
        "admission_maximum_normalized_wer": 0.05,
        "source_summaries": source_summaries,
        "rover_summary": _summary(rows),
        "rover_admission": "not_admitted",
        "clinical_truth_asserted": False,
        "confidence": None,
        "candidate_selection_performed": True,
        "limitations": [
            "ROVER is a text-level voting baseline and does not use acoustic evidence.",
            "With two candidates, tied substitutions resolve to the declared pivot.",
            "A voted clinical token can be wrong even when multiple systems agree.",
            "Any source model failure remains visible and prevents admission.",
        ],
        "cases": rows,
    }
    with output.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(payload, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", nargs="+", required=True)
    parser.add_argument("--pivot-backend", required=True)
    parser.add_argument("--suite", default="evaluation/detailed-suite-v2.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.reports, args.out, args.pivot_backend, args.suite)[
                "rover_summary"
            ],
            indent=2,
        )
    )
