"""Structured note-quality metrics with explicit failure accounting."""


def measure(*, factuality, exact_preservation, section_correctness, length, duplication, omissions, unsafe_claims, latency_ms, timed_out=False):
    values = (factuality, exact_preservation, section_correctness, duplication, omissions, unsafe_claims)
    if any(not isinstance(value, (int, float)) or value < 0 for value in values) or latency_ms < 0:
        raise ValueError('invalid_note_metric')
    return {'factuality': factuality, 'exact_preservation': exact_preservation,
            'section_correctness': section_correctness, 'length': length,
            'duplication': duplication, 'omissions': omissions,
            'unsafe_claims': unsafe_claims, 'latency_ms': latency_ms,
            'timed_out': bool(timed_out), 'clinical_accuracy_claim': False}
