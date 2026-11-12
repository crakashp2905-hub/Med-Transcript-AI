"""Non-destructive ASR suggestions; raw segments are never overwritten."""

from copy import deepcopy

from services.review.clinical import MEDICATION, quantity_signature


def suggest(raw_segments, suggestions=None):
    if not isinstance(raw_segments, list):
        raise ValueError("raw_segments_required")
    suggestions = [] if suggestions is None else suggestions
    if not isinstance(suggestions, list):
        raise ValueError("suggestions_must_be_list")
    output_suggestions = []
    for item in suggestions:
        if not isinstance(item, dict):
            raise ValueError("suggestion_must_be_object")
        index = item.get("segment_index")
        proposed = item.get("suggested_text")
        if type(index) is not int or not 0 <= index < len(raw_segments):
            raise ValueError("suggestion_segment_index_invalid")
        if not isinstance(proposed, str):
            raise ValueError("suggestion_text_required")
        original = raw_segments[index].get("text")
        if not isinstance(original, str):
            raise ValueError("raw_segment_text_required")
        reasons = []
        if [value.lower() for value in MEDICATION.findall(original)] != [
            value.lower() for value in MEDICATION.findall(proposed)
        ]:
            reasons.append("medication_substitution_requires_review")
        if quantity_signature(original) != quantity_signature(proposed):
            reasons.append("numeric_or_unit_substitution_requires_review")
        output_suggestions.append(
            {
                **deepcopy(item),
                "original_text": original,
                "review_required": True,
                "risk_reasons": reasons,
                "adopted": False,
            }
        )
    return {
        "raw_segments": deepcopy(raw_segments),
        "correction_suggestions": output_suggestions,
        "postprocessing_status": "advisory_only",
        "preserves_source_words": True,
        "automatic_adoption": False,
    }
