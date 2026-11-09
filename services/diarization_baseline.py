"""Pinned development DER baseline; not a reliability claim."""


WEIGHTED_DER_BASELINE = 0.5091


def baseline_report():
    return {'schema_version': 'weighted_der_baseline_v1', 'weighted_der': WEIGHTED_DER_BASELINE,
            'baseline_status': 'reproduced_development_baseline', 'heuristic_reliable': False,
            'clinical_speaker_accuracy': False, 'requires_independent_scoring': True}
