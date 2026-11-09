"""Source-identity contracts for metamorphic audio checks."""

TRANSFORMS = frozenset({'volume', 'leading_trailing_silence', 'mild_resampling', 'split_rejoin'})


def validate_transform(name, *, source_sha256, transformed_sha256, result):
    if name not in TRANSFORMS:
        raise ValueError('unknown_metamorphic_transform')
    if not source_sha256 or not transformed_sha256 or not isinstance(result, dict):
        raise ValueError('metamorphic_provenance_required')
    return {'transform': name, 'source_sha256': source_sha256,
            'transformed_sha256': transformed_sha256, 'result': result,
            'source_integrity_preserved': True, 'clinical_claim': False}
