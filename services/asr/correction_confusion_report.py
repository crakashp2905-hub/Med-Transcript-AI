"""Build grouped, cross-fitted ASR correction examples from a saved run."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from services.evaluation import tokens
from services.immutable_reports import publish_json_once

try:
    from rapidfuzz.distance import Levenshtein
except ImportError:  # The utility is supplied by the repository's optional ASR extra.
    Levenshtein = None


DEFAULT_MANIFEST = Path("evaluation/datasets/meddistract-detailed-v1/manifest.json")
DEFAULT_RECEIPT = Path(
    "evaluation/runs/meddistract-detailed-v7/faster-whisper-tiny.en.fixed.json"
)
DEFAULT_OUTPUT = Path(
    "evaluation/runs/meddistract-detailed-v7/correction-tables/"
    "tiny-en-grouped-confusion-table-v1.json"
)
RESERVED_PREFIXES = (
    "day5_consultation05",
    "day5_consultation06",
    "day5_consultation07",
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _contexts(reference, index, radius=2):
    start = max(0, index - radius)
    end = min(len(reference), index + radius + 1)
    return reference[start:index], reference[index + 1 : end]


def build_confusion_report(
    manifest_path=DEFAULT_MANIFEST, receipt_path=DEFAULT_RECEIPT
):
    manifest_path, receipt_path = Path(manifest_path), Path(receipt_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        manifest.get("rights_reviewed") is not True
        or manifest.get("data_class") != "approved_public"
    ):
        raise ValueError("rights_reviewed_public_development_manifest_required")
    if manifest.get("split") != "development_not_independent_acceptance":
        raise ValueError("development_manifest_required")
    if (
        receipt.get("complete") is not True
        or receipt.get("clinical_acceptance") is not False
    ):
        raise ValueError("complete_non_acceptance_receipt_required")
    if receipt.get("manifest_sha256") != _sha(manifest_path):
        raise ValueError("receipt_manifest_hash_mismatch")
    if Levenshtein is None:
        raise ValueError("rapidfuzz_required_for_crossfit_alignment")

    source_cases = {row["group_id"]: row for row in manifest["cases"]}
    receipt_cases = receipt.get("cases")
    if not isinstance(receipt_cases, list) or len(receipt_cases) != len(source_cases):
        raise ValueError("complete_matching_case_set_required")
    groups = sorted({row.get("foreground_id") for row in receipt_cases})
    if None in groups or len(groups) < 2:
        raise ValueError("multiple_consultation_groups_required")
    if any(
        any(group.startswith(prefix) for prefix in RESERVED_PREFIXES)
        for group in groups
    ):
        raise ValueError("reserved_acceptance_group_forbidden")

    folds = {
        group: [candidate for candidate in groups if candidate != group]
        for group in groups
    }
    rows = []
    totals = {"substitution": 0, "deletion": 0, "insertion": 0}
    aligned_edits = 0
    reference_words = 0
    seen = set()
    for case in receipt_cases:
        case_id = case.get("id")
        source = source_cases.get(case_id)
        if source is None or case_id in seen:
            raise ValueError("receipt_case_identity_mismatch")
        seen.add(case_id)
        if (
            case.get("foreground_id") != source.get("foreground_id")
            or case.get("condition") != source.get("condition")
            or case.get("input_sha256") != source.get("audio_sha256")
        ):
            raise ValueError("receipt_source_binding_mismatch")
        if not isinstance(case.get("reference"), str) or not isinstance(
            case.get("hypothesis"), str
        ):
            raise ValueError("textual_reference_and_hypothesis_required")
        reference = tokens(case["reference"])
        hypothesis = [] if case.get("failed") else tokens(case["hypothesis"])
        editops = Levenshtein.editops(reference, hypothesis)
        edits = [
            (
                {
                    "replace": "substitution",
                    "delete": "deletion",
                    "insert": "insertion",
                }[edit.tag],
                edit.src_pos,
                edit.dest_pos if edit.tag != "delete" else None,
            )
            for edit in editops
        ]
        if len(edits) != case.get("normalized_edits") or len(reference) != case.get(
            "reference_words"
        ):
            raise ValueError("saved_edit_counts_do_not_reconcile")
        group = case["foreground_id"]
        reference_words += len(reference)
        aligned_edits += len(edits)
        for operation, ref_index, hyp_index in edits:
            totals[operation] += 1
            anchor = min(ref_index, len(reference) - 1) if reference else 0
            left, right = _contexts(reference, anchor)
            rows.append(
                {
                    "case_id": case_id,
                    "consultation_group": group,
                    "condition": case["condition"],
                    "audio_sha256": case["input_sha256"],
                    "reference_sha256": hashlib.sha256(
                        case["reference"].encode("utf-8")
                    ).hexdigest(),
                    "fold_id": f"leave_group_out:{group}",
                    "training_groups_for_fold": folds[group],
                    "held_out_group": group,
                    "operation": operation,
                    "reference_index": ref_index,
                    "hypothesis_index": hyp_index,
                    "reference_token": reference[ref_index]
                    if operation != "insertion"
                    else None,
                    "hypothesis_token": hypothesis[hyp_index]
                    if hyp_index is not None
                    else None,
                    "reference_left_context": left,
                    "reference_right_context": right,
                }
            )
    if seen != set(source_cases):
        raise ValueError("receipt_missing_source_cases")

    return {
        "schema_version": "asr_grouped_correction_confusion_table_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "model_fit": False,
        "inference_executed": False,
        "source_commit": _source_commit(),
        "inputs": {
            "manifest_path": manifest_path.as_posix(),
            "manifest_sha256": _sha(manifest_path),
            "receipt_path": receipt_path.as_posix(),
            "receipt_sha256": _sha(receipt_path),
            "suite_sha256": receipt.get("suite_sha256"),
            "license": manifest.get("license"),
            "attribution": manifest.get("attribution"),
        },
        "split_protocol": {
            "method": "leave_one_foreground_consultation_group_out",
            "consultation_groups": groups,
            "folds": {
                group: {"training_groups": folds[group], "held_out_group": group}
                for group in groups
            },
            "case_conditions_are_kept_in_the_same_foreground_group": True,
            "reserved_acceptance_groups_used": [],
            "speaker_site_device_and_model_training_independence_established": False,
        },
        "summary": {
            "case_count": len(seen),
            "consultation_group_count": len(groups),
            "reference_words": reference_words,
            "normalized_edits": aligned_edits,
            "substitutions": totals["substitution"],
            "deletions": totals["deletion"],
            "insertions": totals["insertion"],
            "confusion_rows": len(rows),
            "failed_cases": sum(bool(case.get("failed")) for case in receipt_cases),
            "wer": aligned_edits / reference_words if reference_words else None,
        },
        "training_table": rows,
        "limitations": [
            "This is a source-linked candidate table, not a fitted or evaluated correction model.",
            "The eight development consultation groups are small and do not establish speaker, site, device, or model-training independence.",
            "References are not clinician-adjudicated clinical gold; no clinical correctness claim is made.",
            "Only error rows are included; a future training recipe must retain correct examples and fit transforms within each training fold.",
            "No reserved acceptance labels or audio were used.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_confusion_report(args.manifest, args.receipt)
    published = publish_json_once(args.output, report)
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "sha256": _sha(args.output),
                "cases": published["summary"]["case_count"],
                "rows": published["summary"]["confusion_rows"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
