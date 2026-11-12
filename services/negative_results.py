"""Negative-result record kept separate from reserved acceptance materials."""


def record(*, method, baseline, outcome, acceptance_materials_modified=False):
    if outcome not in {"slower", "less_accurate", "equivalent", "better"}:
        raise ValueError("invalid_outcome")
    if acceptance_materials_modified:
        raise ValueError("acceptance_materials_are_reserved")
    return {
        "method": method,
        "baseline": baseline,
        "outcome": outcome,
        "acceptance_materials_modified": False,
    }
