from services.role_correction import preview


def test_role_correction_preview_is_source_linked_and_requires_approval():
    result = preview([{'id': 't1', 'speaker': 'spk1', 'role': 'unknown', 'source_ref': 'audio#1'}], {'spk1': 'clinician'})
    assert result['changes'][0]['source_ref'] == 'audio#1'
    assert result['changes'][0]['to'] == 'clinician'
    assert result['approval_required'] is True
