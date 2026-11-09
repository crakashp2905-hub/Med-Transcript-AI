"""Frozen, source-only chunk selection strategies."""

STRATEGIES = frozenset({'fixed_30s', 'pause_aware', 'overlap_aware', 'source_time_only'})


def freeze_strategy(strategy, parameters, *, source_only=True, scored=False):
    if strategy not in STRATEGIES:
        raise ValueError('unknown_chunk_strategy')
    if not source_only or scored:
        raise ValueError('oracle_free_selection_required')
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError('frozen_parameters_required')
    return {'strategy': strategy, 'parameters': dict(parameters), 'source_only': True,
            'frozen_before_scoring': True, 'hypothesis_used_for_selection': False}
