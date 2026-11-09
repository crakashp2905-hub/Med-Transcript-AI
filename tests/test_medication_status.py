from services.medication_status import classify


def test_medication_status_preserves_temporality_without_current_prescription_inference():
    assert classify('Patient stopped warfarin last month')['status'] == 'stopped'
    assert classify('Plan to restart metformin next week')['status'] == 'restarted'
    result = classify('Patient takes an unknown medication')
    assert result['current_prescription_inferred'] is False and result['requires_review'] is True
