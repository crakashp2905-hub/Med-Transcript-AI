"""Deterministic clinical fact mutation definitions."""

MUTATION_KINDS = frozenset({"single", "pairwise", "temporal_swap", "coreference_swap"})


def generate(fact_ids, kind):
    if kind not in MUTATION_KINDS:
        raise ValueError("unknown_mutation_kind")
    if not fact_ids:
        raise ValueError("fact_ids_required")
    return {
        "kind": kind,
        "fact_ids": list(fact_ids),
        "one_change_at_a_time": kind == "single",
        "source": "synthetic_developer_case",
        "clinical_gold": False,
    }
