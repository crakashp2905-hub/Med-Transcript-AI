"""Finite, meaning-preserving display normalization for recognized quantities."""

from services.review.clinical import QUANTITY, quantity_signature


def propose_quantity_format(text):
    if not isinstance(text, str):
        raise ValueError("quantity_text_required")
    formatted = QUANTITY.sub(
        lambda match: f"{match['value']} {match['unit'].lower()}", text
    )
    if quantity_signature(text) != quantity_signature(formatted):
        raise ValueError("quantity_format_changed_numeric_meaning")
    return {
        "original_text": text,
        "formatted_candidate": formatted,
        "changed": formatted != text,
        "status": "formatting_candidate_only",
        "automatic_adoption": False,
        "unit_added": False,
        "quantity_signature_preserved": True,
    }
