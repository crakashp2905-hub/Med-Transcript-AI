from services.review.clinical import medication_associations


def test_two_medications_keep_distinct_dose_and_frequency_associations():
    result = medication_associations('Take warfarin 0.5 mg daily and metformin 500 mg twice daily.')
    assert result == [
        {'medication_name': 'warfarin', 'dose': '0.5 mg', 'frequency': 'daily', 'ambiguous': False},
        {'medication_name': 'metformin', 'dose': '500 mg', 'frequency': 'twice daily', 'ambiguous': False},
    ]
