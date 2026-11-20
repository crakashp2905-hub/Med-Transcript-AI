"""Reconcile saved paired terminology-bias arms over the frozen development cohort."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from services.immutable_reports import publish_json_once


MANIFEST = Path("evaluation/datasets/meddistract-detailed-v1/manifest.json")
LOCK = Path("evaluation/datasets/meddistract-detailed-v1/lock.json")
RECEIPT = Path("evaluation/runs/meddistract-detailed-v7/matched-ablation-v3.json")
LEXICON = Path("evaluation/lexicons/clinical-english-v1-e01.json")
RESERVATION = Path("evaluation/acceptance-reservation-v1.json")
OUTPUT = Path(
    "evaluation/runs/meddistract-detailed-v7/lexicon-evaluation/"
    "paracetamol-full-cohort-v1.json"
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _reference(case):
    return " ".join(
        re.sub(r"<[^>]+>", "", turn["reference"]) for turn in case["reference_turns"]
    )


def _term_count(text, term):
    return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text, re.I))


def _arm_rows(receipt, arm):
    value = receipt.get("arm_outputs", {}).get(arm)
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
        raise ValueError("complete_saved_ablation_arm_required")
    return value["cases"]


def build_cohort_report(
    manifest_path=MANIFEST,
    lock_path=LOCK,
    receipt_path=RECEIPT,
    lexicon_path=LEXICON,
    reservation_path=RESERVATION,
):
    manifest_path, lock_path = Path(manifest_path), Path(lock_path)
    receipt_path, lexicon_path = Path(receipt_path), Path(lexicon_path)
    reservation_path = Path(reservation_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lexicon = json.loads(lexicon_path.read_text(encoding="utf-8"))
    reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
    manifest_sha = _sha(manifest_path)
    if (
        manifest.get("data_class") != "approved_public"
        or manifest.get("rights_reviewed") is not True
        or manifest.get("split") != "development_not_independent_acceptance"
        or lock.get("manifest_sha256") != manifest_sha
        or receipt.get("complete") is not True
        or receipt.get("clinical_acceptance") is not False
        or receipt.get("bindings", {}).get("manifest_sha256") != manifest_sha
    ):
        raise ValueError("locked_rights_reviewed_development_inputs_required")
    reserved = set(reservation.get("reserved_groups", []))
    source_cases = {row["group_id"]: row for row in manifest.get("cases", [])}
    if any(
        case.get("foreground_id") in reserved or case.get("donor_id") in reserved
        for case in source_cases.values()
    ):
        raise ValueError("reserved_acceptance_group_in_eval_source")
    entries = lexicon.get("entries", [])
    terms = [row.get("term") for row in entries]
    if len(terms) != 1 or not isinstance(terms[0], str) or not terms[0].strip():
        raise ValueError("single_pinned_lexicon_term_required")
    term = terms[0].strip()
    expected_lexicon_sha = receipt.get("bindings", {}).get("lexicon_sha256")
    if expected_lexicon_sha != _sha(lexicon_path):
        raise ValueError("receipt_lexicon_hash_mismatch")
    configuration = receipt["arm_outputs"]["terminology_only"].get("configuration", {})
    if (
        configuration.get("component_parameters", {}).get("lexicon_sha256")
        != expected_lexicon_sha
    ):
        raise ValueError("terminology_arm_lexicon_binding_mismatch")
    if configuration.get("component_parameters", {}).get("hotwords") != term:
        raise ValueError("terminology_arm_term_mismatch")

    baseline = _arm_rows(receipt, "fixed_baseline")
    biased = _arm_rows(receipt, "terminology_only")
    if len(baseline) != len(source_cases) or len(biased) != len(source_cases):
        raise ValueError("full_cohort_paired_arms_required")
    arms = {
        "baseline": {row["group_id"]: row for row in baseline},
        "biased": {row["group_id"]: row for row in biased},
    }
    if any(
        len(rows) != len(source_cases) or set(rows) != set(source_cases)
        for rows in arms.values()
    ):
        raise ValueError("paired_arm_case_identity_mismatch")

    exact_cases = []
    aggregates = {}
    for arm, arm_cases in arms.items():
        positive_occurrences = positive_recalled = 0
        positive_cases = positive_case_hits = 0
        negative_cases = negative_case_insertions = negative_false_occurrences = 0
        uncertain_term_cases = uncertain_case_insertions = (
            uncertain_false_occurrences
        ) = 0
        edits = words = failures = 0
        condition_metrics = {}
        for case_id, result in sorted(arm_cases.items()):
            source = source_cases[case_id]
            reference = _reference(source)
            reference_sha = hashlib.sha256(reference.encode("utf-8")).hexdigest()
            if (
                result.get("audio_sha256") != source.get("audio_sha256")
                or result.get("reference_sha256") != reference_sha
                or result.get("foreground_id") != source.get("foreground_id")
                or result.get("condition") != source.get("condition")
            ):
                raise ValueError("saved_arm_source_hash_mismatch")
            uncertain_text = " ".join(
                turn["reference"]
                for turn in source.get("reference_turns", [])
                if turn.get("uncertain_reference") is True
            )
            certain_text = " ".join(
                turn["reference"]
                for turn in source.get("reference_turns", [])
                if turn.get("uncertain_reference") is not True
            )
            certain_count = _term_count(certain_text, term)
            uncertain_count = _term_count(uncertain_text, term)
            hypothesis = "" if result.get("failed") else result.get("hypothesis", "")
            if not isinstance(hypothesis, str):
                raise ValueError("saved_hypothesis_text_required")
            hypothesis_count = _term_count(hypothesis, term)
            is_uncertain = certain_count == 0 and uncertain_count > 0
            if is_uncertain:
                uncertain_term_cases += 1
                uncertain_case_insertions += hypothesis_count > 0
                uncertain_false_occurrences += hypothesis_count
            elif certain_count:
                positive_occurrences += certain_count
                positive_recalled += min(certain_count, hypothesis_count)
                positive_cases += 1
                positive_case_hits += hypothesis_count > 0
            else:
                negative_cases += 1
                negative_case_insertions += hypothesis_count > 0
                negative_false_occurrences += hypothesis_count
            case_edits = result.get("normalized_edits")
            case_words = result.get("reference_words")
            if (
                type(case_edits) is not int
                or case_edits < 0
                or type(case_words) is not int
                or case_words <= 0
            ):
                raise ValueError("saved_arm_wer_metrics_invalid")
            edits += case_edits
            words += case_words
            failures += bool(result.get("failed"))
            metrics = condition_metrics.setdefault(
                result["condition"],
                {"case_count": 0, "normalized_edits": 0, "reference_words": 0},
            )
            metrics["case_count"] += 1
            metrics["normalized_edits"] += case_edits
            metrics["reference_words"] += case_words
            exact_cases.append(
                {
                    "arm": arm,
                    "group_id": case_id,
                    "foreground_id": source["foreground_id"],
                    "condition": source["condition"],
                    "audio_sha256": source["audio_sha256"],
                    "reference_sha256": reference_sha,
                    "failed": bool(result.get("failed")),
                    "certain_reference_term_occurrences": certain_count,
                    "uncertain_reference_term_occurrences": uncertain_count,
                    "hypothesis_term_occurrences": hypothesis_count,
                    "term_reference_class": "uncertain_only"
                    if is_uncertain
                    else "positive"
                    if certain_count
                    else "negative_control",
                }
            )
        source_arm = "fixed_baseline" if arm == "baseline" else "terminology_only"
        source_summary = receipt.get("comparison", {}).get("arms", {}).get(source_arm)
        if (
            not isinstance(source_summary, dict)
            or source_summary.get("sample_count") != len(arm_cases)
            or source_summary.get("failed_samples") != failures
            or source_summary.get("reference_words") != words
            or source_summary.get("normalized_edits") != edits
        ):
            raise ValueError("saved_arm_wer_reconciliation_failed")
        aggregates[arm] = {
            "case_count": len(arm_cases),
            "reference_words": words,
            "normalized_edits": edits,
            "normalized_wer": edits / words if words else None,
            "failures": failures,
            "certain_positive_term_occurrences": positive_occurrences,
            "recalled_positive_term_occurrences": positive_recalled,
            "positive_occurrence_recall": positive_recalled / positive_occurrences
            if positive_occurrences
            else None,
            "positive_case_count": positive_cases,
            "positive_cases_with_term": positive_case_hits,
            "negative_control_case_count": negative_cases,
            "negative_cases_with_term_in_hypothesis": negative_case_insertions,
            "negative_case_false_insertion_rate": negative_case_insertions
            / negative_cases
            if negative_cases
            else None,
            "negative_control_false_term_occurrences": negative_false_occurrences,
            "uncertain_only_term_case_count": uncertain_term_cases,
            "uncertain_only_cases_with_term_in_hypothesis": uncertain_case_insertions,
            "uncertain_only_hypothesis_term_occurrences": uncertain_false_occurrences,
            "by_condition": {
                condition: {
                    **values,
                    "normalized_wer": values["normalized_edits"]
                    / values["reference_words"]
                    if values["reference_words"]
                    else None,
                }
                for condition, values in sorted(condition_metrics.items())
            },
        }

    return {
        "schema_version": "asr_lexicon_bias_full_cohort_v1",
        "complete": True,
        "status": "development_cohort_diagnostic_not_clinical_validation",
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "inference_executed": False,
        "model_fit": False,
        "source_commit": _commit(),
        "term": term,
        "bindings": {
            "manifest_sha256": manifest_sha,
            "dataset_lock_sha256": _sha(lock_path),
            "source_run_sha256": _sha(receipt_path),
            "lexicon_sha256": expected_lexicon_sha,
            "reservation_sha256": _sha(reservation_path),
        },
        "paired_arms": ["baseline", "biased"],
        "scoring": {
            "wer": "existing failure-inclusive normalized word edit rate; unchanged primary endpoint",
            "term_match": "case-insensitive whole-token exact match",
            "positive_recall": "reference occurrences from non-uncertain turns, capped by hypothesis occurrence count",
            "false_insertion": "exact term occurrences in cases with no certain reference occurrence; uncertain-only cases are excluded",
        },
        "reserved_acceptance_groups_used": [],
        "summary": aggregates,
        "cases": exact_cases,
        "limitations": [
            "One licensed seed term and eight foreground consultations provide a narrow development slice.",
            "References are not independently clinician-adjudicated clinical gold; exact lexical occurrence is not clinical term correctness.",
            "Occurrence counting is a transparent lexical diagnostic, not span alignment or a calibrated term detector.",
            "No model was trained, no new inference ran, and no inference profile is promoted.",
            "Results do not establish the <=5% WER gate or any clinical safety gate.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = publish_json_once(args.out, build_cohort_report())
    print(
        json.dumps(
            {
                "output": args.out.as_posix(),
                "sha256": _sha(args.out),
                "summary": report["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
