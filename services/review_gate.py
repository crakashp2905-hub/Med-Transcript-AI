"""Aggregate conditions that require human review before approval."""

REVIEW_REASONS = frozenset({'incomplete_model', 'cross_utterance_pronoun', 'ambiguous_medication_attachment', 'unknown_speaker'})


def evaluate(flags):
    reasons = sorted(set(flags) & REVIEW_REASONS)
    return {'review_required': bool(reasons), 'reasons': reasons, 'approval_allowed': not reasons}
