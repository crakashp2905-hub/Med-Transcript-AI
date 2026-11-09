"""Novel-component ablation configuration envelope."""

COMPONENTS = ('relations', 'negation_scope', 'temporality', 'evidence_coverage', 'model_opinion', 'confidence_abstention')


def configure(**enabled):
    if set(enabled) != set(COMPONENTS) or any(not isinstance(value, bool) for value in enabled.values()):
        raise ValueError('complete_boolean_ablation_required')
    return {'components': enabled, 'active_count': sum(enabled.values())}
