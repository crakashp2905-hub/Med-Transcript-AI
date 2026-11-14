"""Failure-inclusive ASR slices keyed only by explicit manifest labels."""

import re
from collections import defaultdict

from services.evaluation_metrics import score_text


def _summary(samples):
    reference_words = sum(row["reference_words"] for row in samples)
    edits = sum(row["normalized_edits"] for row in samples)
    return {
        "case_count": len(samples),
        "failed_case_count": sum(row["status"] == "failed" for row in samples),
        "reference_words": reference_words,
        "normalized_edits": edits,
        "normalized_wer": edits / reference_words if reference_words else None,
    }


def build_subgroup_analysis(manifest_samples, result_rows):
    """Aggregate exact case rows by group, role, noise and uncertainty labels.

    Clinical term scores require an explicit per-sample `clinical_terms` list;
    absent annotations are counted and never treated as an error-free slice.
    """
    if not isinstance(manifest_samples, list) or not isinstance(result_rows, list):
        raise ValueError("subgroup_inputs_must_be_lists")
    samples_by_id = {row.get("sample_id"): row for row in manifest_samples}
    results_by_id = {row.get("sample_id"): row for row in result_rows}
    if (
        None in samples_by_id
        or len(samples_by_id) != len(manifest_samples)
        or set(samples_by_id) != set(results_by_id)
    ):
        raise ValueError("subgroup_case_coverage_mismatch")
    strata = {
        key: defaultdict(list)
        for key in ("consultation", "speaker_role", "noise_condition", "uncertainty")
    }
    term_counts = defaultdict(
        lambda: {
            "reference_occurrences": 0,
            "matched_occurrences": 0,
            "hypothesis_occurrences": 0,
        }
    )
    labelled_samples = 0
    for case_id, sample in samples_by_id.items():
        result = results_by_id[case_id]
        reference = sample["reference"]
        hypothesis = (
            result.get("hypothesis", "") if result.get("status") == "completed" else ""
        )
        metric_row = {
            "reference_words": len(
                re.findall(r"\d+(?:\.\d+)?|[a-z]+(?:['-][a-z]+)*", reference.lower())
            ),
            "normalized_edits": score_text(reference, hypothesis)["word_edits"],
            "status": result.get("status"),
        }
        labels = {
            "consultation": str(sample["group_id"]),
            "speaker_role": str(sample.get("speaker_role", "unknown")),
            "noise_condition": str(sample.get("noise_condition", "unspecified")),
            "uncertainty": "uncertain"
            if sample.get("reference_uncertain") is True
            else "not_flagged",
        }
        for dimension, label in labels.items():
            strata[dimension][label].append(metric_row)
        terms = sample.get("clinical_terms")
        if isinstance(terms, list) and terms:
            labelled_samples += 1
            ref_lower, hyp_lower = reference.lower(), hypothesis.lower()
            for term in terms:
                if not isinstance(term, str) or not term.strip():
                    raise ValueError("clinical_term_annotation_invalid")
                key = term.strip().lower()
                ref_count = len(
                    re.findall(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", ref_lower)
                )
                hyp_count = len(
                    re.findall(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", hyp_lower)
                )
                term_counts[key]["reference_occurrences"] += ref_count
                term_counts[key]["hypothesis_occurrences"] += hyp_count
                term_counts[key]["matched_occurrences"] += min(ref_count, hyp_count)
    return {
        "schema_version": "asr_subgroup_metrics_v1",
        "denominator_policy": "all_manifest_cases_including_failed_cases_as_empty_hypotheses",
        "by_dimension": {
            dimension: {label: _summary(rows) for label, rows in sorted(groups.items())}
            for dimension, groups in strata.items()
        },
        "clinical_term_analysis": {
            "labelled_case_count": labelled_samples,
            "unlabelled_case_count": len(manifest_samples) - labelled_samples,
            "coverage_fraction": labelled_samples / len(manifest_samples)
            if manifest_samples
            else 0.0,
            "terms": {
                term: {
                    **counts,
                    "missed_occurrences": counts["reference_occurrences"]
                    - counts["matched_occurrences"],
                    "spurious_occurrences": max(
                        0,
                        counts["hypothesis_occurrences"]
                        - counts["matched_occurrences"],
                    ),
                }
                for term, counts in sorted(term_counts.items())
            },
        },
    }
