from services.uncertainty_classifier import classify


def test_uncertainty_classifier_does_not_promote_hedged_or_missing_data():
    assert classify('Maybe chest pain.')['assertion'] == 'uncertain'
    assert classify('') == {'assertion': 'unknown', 'value': None, 'requires_review': True}
    assert classify('Chest pain reported.')['assertion'] == 'affirmed'
