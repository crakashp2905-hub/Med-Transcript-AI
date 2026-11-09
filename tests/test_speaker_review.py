from services.speaker_review import plan


def test_speaker_review_separates_unambiguous_and_ambiguous_turns():
    result = plan([{'id': 'a', 'ambiguous': False}, {'id': 'b', 'ambiguous': True}])
    assert result['exemplar_playback'] is True
    assert result['batch_confirm_ids'] == ['a']
    assert result['isolated_ambiguous_ids'] == ['b']
    assert result['approval_required'] is True
