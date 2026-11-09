"""Fixed-case comparison envelope for verification methods."""

METHODS = ('lexical_rules', 'relation_rules', 'llm_only', 'combined_evidence_graph')


def compare(cases, results):
    if not isinstance(cases, list) or not cases or set(results) != set(METHODS):
        raise ValueError('identical_cases_and_methods_required')
    if any(len(values) != len(cases) for values in results.values()):
        raise ValueError('case_alignment_required')
    return {'cases': cases, 'methods': results, 'clinical_sensitivity_claim': False}
