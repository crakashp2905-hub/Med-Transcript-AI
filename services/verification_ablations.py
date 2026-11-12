"""Deterministic ablation report envelope for verification policies."""

ARMS = (
    "basic_lexical_rules",
    "relational_rules",
    "local_verifier",
    "rules_plus_local_verifier",
    "deterministic_source_only",
)


def report(results):
    if not isinstance(results, dict) or set(results) != set(ARMS):
        raise ValueError("complete_ablation_arms_required")
    for arm, value in results.items():
        if not isinstance(value, dict):
            raise ValueError("ablation_result_required")
        for key in ("tp", "fp", "fn", "tn", "abstentions", "timeouts", "malformed"):
            if key not in value:
                raise ValueError(f"missing_{key}:{arm}")
    return {"arms": results, "clinical_sensitivity_claim": False}
