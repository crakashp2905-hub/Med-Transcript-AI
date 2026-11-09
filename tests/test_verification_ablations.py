from services.verification_ablations import ARMS, report


def test_ablation_report_requires_all_policy_arms_and_failure_dimensions():
    row = {'tp': 1, 'fp': 0, 'fn': 1, 'tn': 2, 'abstentions': 0, 'timeouts': 1, 'malformed': 0}
    result = report({arm: row.copy() for arm in ARMS})
    assert set(result['arms']) == set(ARMS)
    assert result['arms']['rules_plus_local_verifier']['timeouts'] == 1
    assert result['clinical_sensitivity_claim'] is False
