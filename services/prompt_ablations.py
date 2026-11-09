"""Separate, frozen prompt ablation definitions."""

ABLATIONS = frozenset({'smaller_prompt', 'subtask_decomposition', 'grammar_constrained', 'chunked_facts'})


def define(name, *, prompt_digest, input_digest, active=False):
    if name not in ABLATIONS:
        raise ValueError('unknown_prompt_ablation')
    if not prompt_digest or not input_digest:
        raise ValueError('ablation_digests_required')
    return {'name': name, 'prompt_digest': prompt_digest, 'input_digest': input_digest,
            'active_model_policy_changed': bool(active), 'clinical_acceptance': False}
