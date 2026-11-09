from services.clinical_metrics import evaluate


def test_metrics_report_raw_normalized_and_clinical_term_dimensions():
    result = evaluate(
        'No allergy. Dose 0.5 mg Warfarin.',
        'No allergy. Dose 5 mcg Warfarin.',
        [{'category': 'medication', 'concept': 'warfarin', 'subject': 'patient', 'assertion': 'affirmed', 'temporality': 'current'}],
        [{'category': 'medication', 'concept': 'warfarin', 'subject': 'patient', 'assertion': 'affirmed', 'temporality': 'current'}],
    )
    assert 'raw_wer' in result and 'normalized_wer' in result
    assert 'character_error_rate' in result
    assert result['by_category']['medication']['true_positive'] == 1
    assert result['reference_words'] > 0
