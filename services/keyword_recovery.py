"""ASR keyword recovery comparison without unsupported automatic merging."""


def compare(candidates, supported_terms):
    if not isinstance(candidates, dict) or not isinstance(supported_terms, set):
        raise ValueError('candidate_inputs_required')
    rows = {}
    for model, terms in candidates.items():
        rows[model] = {'terms': list(terms), 'supported': [term for term in terms if term in supported_terms],
                       'unsupported': [term for term in terms if term not in supported_terms]}
    return {'models': rows, 'automatic_merge': False, 'selection_required': True}
