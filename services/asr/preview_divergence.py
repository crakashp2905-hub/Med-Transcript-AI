"""Diagnostic comparison between a provisional preview and a final transcript.

This report is informational only. It never creates or changes an encounter
transcript, approval, or clinical verdict.
"""

import re
import unicodedata


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)?", normalized, flags=re.UNICODE)


def _edit_distance(left: list[str], right: list[str]) -> int:
    """Memory-bounded word Levenshtein distance."""
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        current = [i]
        for j, b in enumerate(right, start=1):
            current.append(
                min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b))
            )
        previous = current
    return previous[-1]


def compare_preview_to_final(preview: dict, final: dict) -> dict:
    """Return a non-approvable divergence diagnostic for paired ASR results."""
    if preview.get("status") != "provisional_not_a_source_version":
        raise ValueError("preview_result_not_provisional")
    if preview.get("approvable") is not False:
        raise ValueError("preview_must_be_unapprovable")
    if not final.get("transcript_version_id"):
        raise ValueError("final_transcript_version_required")
    if preview.get("profile_sha256") != final.get("profile_sha256"):
        raise ValueError("profile_mismatch")
    preview_tokens = _tokens(
        " ".join(s.get("text", "") for s in preview.get("provisional_segments", []))
    )
    final_tokens = _tokens(" ".join(s.get("text", "") for s in final.get("segments", [])))
    distance = _edit_distance(preview_tokens, final_tokens)
    denominator = max(len(preview_tokens), len(final_tokens), 1)
    return {
        "kind": "preview_final_divergence",
        "diagnostic_only": True,
        "approvable": False,
        "preview_input_sha256": preview.get("input_sha256"),
        "final_transcript_version_id": final["transcript_version_id"],
        "profile_sha256": preview["profile_sha256"],
        "preview_word_count": len(preview_tokens),
        "final_word_count": len(final_tokens),
        "word_edit_count": distance,
        "normalized_word_divergence": distance / denominator,
    }
