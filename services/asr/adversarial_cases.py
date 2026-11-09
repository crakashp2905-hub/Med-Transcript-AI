"""Predeclared synthetic ASR challenge cases; never clinical gold."""

CASES = (
    ('silence', 'digital silence with no speech'),
    ('clipping', 'clipped waveform edges'),
    ('repeated_prompt', 'repeated prompt phrase'),
    ('numerical_dose', '0.5 mg versus 5 mg'),
    ('medical_homophone', 'variant medical homophone'),
    ('ambiguous_utterance', 'intentionally uncertain utterance'),
)


def manifest():
    return {'schema_version': 'asr_adversarial_v1',
            'cases': [{'id': case_id, 'description': description, 'synthetic': True,
                       'clinical_gold': False} for case_id, description in CASES],
            'clinical_gold': False, 'real_patient_release_authorized': False}
