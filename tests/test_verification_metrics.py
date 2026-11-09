from services.verification_metrics import report


def test_verification_metrics_keep_abstentions_and_failures_separate():
    result = report({'dose': {'tp': 2, 'fp': 1, 'fn': 0, 'tn': 3}}, abstentions=1, timeouts=2, malformed=1, incomplete=1)
    assert result['classes']['dose']['tp'] == 2
    assert result['abstentions'] == 1 and result['timeouts'] == 2
    assert result['clinical_sensitivity_claim'] is False
