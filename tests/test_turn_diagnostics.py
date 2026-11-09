from services.turn_diagnostics import diagnose


def test_turn_diagnostics_preserves_short_turns_and_high_cluster_uncertainty():
    result = diagnose([{'start_ms': 0, 'end_ms': 100, 'speaker_id': 'a'}, {'start_ms': 100, 'end_ms': 1000, 'speaker_id': 'b'}, {'start_ms': 1000, 'end_ms': 2000, 'speaker_id': 'c'}], max_expected_clusters=2)
    assert result['short_turns'] == [0]
    assert result['speaker_change_boundaries'] == [1, 2]
    assert result['cluster_status'] == 'unresolved_high_cluster_count'
    assert result['requires_review'] is True
