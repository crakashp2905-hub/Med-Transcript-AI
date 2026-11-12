"""Fail-closed consistency checks for benchmark arithmetic and report status."""

import math


def validate_metric(report):
    edits = report.get("normalized_edits")
    words = report.get("reference_words")
    wer = report.get("normalized_wer")
    if type(edits) is not int or edits < 0 or type(words) is not int or words < 0:
        raise ValueError("invalid_metric_counts")
    if words == 0:
        if edits != 0 or wer is not None:
            raise ValueError("zero_reference_metric_must_be_null")
    else:
        if (
            not isinstance(wer, (int, float))
            or not math.isfinite(wer)
            or wer < 0
            or wer > 1
        ):
            raise ValueError("invalid_metric_percentage")
        if abs(wer - edits / words) > 1e-12:
            raise ValueError("metric_percentage_mismatch")
    failed = report.get("failed_samples", 0)
    samples = report.get("sample_count")
    if (
        type(failed) is not int
        or failed < 0
        or type(samples) is not int
        or samples < 0
        or failed > samples
    ):
        raise ValueError("invalid_failure_denominator")
    if report.get("hash_mismatch") is True:
        raise ValueError("metric_input_hash_mismatch")
    return {
        "valid": True,
        "complete": report.get("complete") is True and failed == 0,
        "normalized_wer": wer,
        "failed_samples": failed,
        "sample_count": samples,
        "real_patient_release_authorized": False,
    }
