"""Fail-closed candidate promotion gate; availability is not admission."""

from services.evaluation import PROJECT_MAX_NORMALIZED_WER


def evaluate_candidate_admission(candidate_id, evidence):
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id_required")
    if not isinstance(evidence, dict):
        raise ValueError("admission_evidence_required")
    reasons = []
    denominator = evidence.get("reference_words")
    edits = evidence.get("normalized_edits")
    failures = evidence.get("failed_samples")
    sample_count = evidence.get("sample_count")
    if (
        type(denominator) is not int
        or denominator <= 0
        or type(edits) is not int
        or edits < 0
        or type(failures) is not int
        or failures < 0
        or type(sample_count) is not int
        or sample_count <= 0
        or failures > sample_count
    ):
        raise ValueError("invalid_failure_inclusive_asr_denominator")
    wer = edits / denominator
    if failures:
        reasons.append("processing_failures_present")
    if wer > PROJECT_MAX_NORMALIZED_WER:
        reasons.append("normalized_wer_exceeds_admission_maximum")
    if evidence.get("source_timing_validated") is not True:
        reasons.append("source_timing_not_validated")
    if evidence.get("license_reviewed") is not True:
        reasons.append("license_not_reviewed")
    if evidence.get("critical_safety_review") != "passed":
        reasons.append("critical_safety_review_not_passed")
    if evidence.get("matched_paired_evaluation") is not True:
        reasons.append("matched_paired_evaluation_missing")
    return {
        "schema_version": "asr_candidate_admission_v1",
        "candidate_id": candidate_id,
        "normalized_wer": wer,
        "maximum_normalized_wer": PROJECT_MAX_NORMALIZED_WER,
        "reference_words": denominator,
        "failed_samples": failures,
        "status": "admitted" if not reasons else "denied",
        "promotion_allowed": not reasons,
        "reasons": reasons,
        "clinical_approval": "not_established_by_asr_admission",
    }
