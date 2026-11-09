"""Research novelty labeling: hypotheses remain hypotheses without fair ablations."""


def classify(method, *, distinct_algorithm=False, fair_ablation=False, improvement=None):
    if not isinstance(method, str) or not method.strip():
        raise ValueError('method_name_required')
    if distinct_algorithm and fair_ablation and improvement is True:
        label = 'supported_development_result'
    else:
        label = 'hypothesis'
    return {'method': method, 'label': label, 'distinct_algorithm': bool(distinct_algorithm),
            'fair_ablation': bool(fair_ablation), 'improvement': improvement,
            'clinical_novelty_claim': False, 'real_patient_release_authorized': False}
