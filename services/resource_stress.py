"""Repeatable bounded stress harness for synthetic local resource checks."""
import gc
import random
import time


def run(work, *, seed=20261109, iterations=100, timeout_seconds=30):
    if not callable(work) or iterations < 1 or iterations > 10000 or timeout_seconds <= 0:
        raise ValueError('invalid_stress_parameters')
    randomizer = random.Random(seed)
    started = time.perf_counter(); completed = 0; failures = []
    try:
        for index in range(iterations):
            if time.perf_counter() - started > timeout_seconds:
                failures.append({'iteration': index, 'reason': 'timeout'})
                break
            try:
                work(randomizer, index)
                completed += 1
            except Exception as exc:
                failures.append({'iteration': index, 'reason': type(exc).__name__})
    finally:
        gc.collect()
    return {'schema_version': 'resource_stress_v1', 'seed': seed, 'requested': iterations,
            'completed': completed, 'failures': failures, 'teardown': 'gc_complete',
            'complete': completed == iterations and not failures}
