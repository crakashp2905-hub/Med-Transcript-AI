from services.model_cards import generate


def test_machine_model_cards_retain_failures_roles_and_limitations():
    report = generate('.')
    assert report['maximum_normalized_wer'] == .05
    assert report['clinical_release_gate'] == 'BLOCKED_EXTERNAL_EVIDENCE_REQUIRED'
    assert len(report['cards']) >= 1
    measured = next(card for card in report['cards'] if card['report_available'])
    assert 'failed_samples' in measured and 'timeouts' in measured and measured['role_metrics']
    assert measured['limitations'] and measured['language'] == 'English'
