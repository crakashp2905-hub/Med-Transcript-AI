"""Simulated workflow quality, cost, and correction metrics."""


def record(*, critical_misses, benign_false_blocks, covered, total, runtime_seconds, memory_bytes, corrections):
    if total < 0 or covered < 0 or covered > total or any(value < 0 for value in
            (critical_misses, benign_false_blocks, runtime_seconds, memory_bytes, corrections)):
        raise ValueError('invalid_workflow_metrics')
    return {'critical_misses': critical_misses, 'benign_false_blocks': benign_false_blocks,
            'coverage': None if total == 0 else covered / total, 'runtime_seconds': runtime_seconds,
            'memory_bytes': memory_bytes, 'reviewer_corrections': corrections}
