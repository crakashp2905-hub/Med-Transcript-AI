from services.adversarial_replay import replay


def test_replay_marks_old_approval_stale_after_source_or_model_change():
    result = replay(
        approved_note="old",
        approved_source_hash="s1",
        approved_model_digest="m1",
        current_source_hash="s2",
        current_model_digest="m2",
        regenerated_note="new",
    )
    assert (
        result["source_changed"] and result["model_changed"] and result["note_changed"]
    )
    assert result["approval_stale"] is True
    assert result["publication_allowed"] is False
