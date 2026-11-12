"""Uncalibrated disagreement diagnostics for local ASR candidate texts."""

from difflib import SequenceMatcher

from services.evaluation import tokens


def compare_hypotheses(rows):
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("at_least_two_hypotheses_required")
    normalized = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("backend_id"), str)
            or not row["backend_id"]
            or not isinstance(row.get("text"), str)
            or row["backend_id"] in normalized
        ):
            raise ValueError("unique_backend_hypotheses_required")
        normalized[row["backend_id"]] = tokens(row["text"])
    backend_ids = sorted(normalized)
    pairs = []
    for left_index, left_id in enumerate(backend_ids):
        for right_id in backend_ids[left_index + 1 :]:
            left, right = normalized[left_id], normalized[right_id]
            matcher = SequenceMatcher(a=left, b=right, autojunk=False)
            edits = sum(
                max(i2 - i1, j2 - j1)
                for tag, i1, i2, j1, j2 in matcher.get_opcodes()
                if tag != "equal"
            )
            denominator = max(len(left), len(right), 1)
            differences = [
                {
                    "left_tokens": left[i1:i2],
                    "right_tokens": right[j1:j2],
                }
                for tag, i1, i2, j1, j2 in matcher.get_opcodes()
                if tag != "equal"
            ]
            pairs.append(
                {
                    "left_backend_id": left_id,
                    "right_backend_id": right_id,
                    "normalized_edit_count": edits,
                    "normalized_disagreement_rate": edits / denominator,
                    "different_spans": differences,
                }
            )
    return {
        "schema_version": "asr_hypothesis_disagreement_v1",
        "backend_ids": backend_ids,
        "pairs": pairs,
        "score_kind": "uncalibrated_text_disagreement_diagnostic",
        "agreement_is_not_truth": True,
        "hypotheses_unchanged": True,
        "candidate_selection_performed": False,
        "clinical_interpretation": "not_assessed",
    }
