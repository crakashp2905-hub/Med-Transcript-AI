"""Pairwise safety regression gate independent of aggregate WER."""


def compare(baseline, candidate):
    required = ('normalized_wer', 'critical_misses', 'omissions', 'false_blocks')
    if any(key not in baseline or key not in candidate for key in required):
        raise ValueError('incomplete_regression_vector')
    if baseline.get('dataset_id') != candidate.get('dataset_id'):
        raise ValueError('incomparable_regression_dataset')
    for key in required:
        if type(baseline[key]) not in (int, float) or baseline[key] < 0 or type(candidate[key]) not in (int, float) or candidate[key] < 0:
            raise ValueError('invalid_regression_metric')
    safety_regressions = {key: candidate[key] - baseline[key] for key in ('critical_misses', 'omissions', 'false_blocks')
                          if candidate[key] > baseline[key]}
    return {'dataset_id': baseline['dataset_id'], 'baseline': baseline, 'candidate': candidate,
            'wer_improved': candidate['normalized_wer'] < baseline['normalized_wer'],
            'safety_regressions': safety_regressions,
            'promotion': 'blocked' if safety_regressions else 'review_required',
            'real_patient_release_authorized': False}
