import pytest

from services.adversarial_replay import replay


@pytest.mark.parametrize("change", ["source", "model", "note"])
def test_replay_marks_approval_stale_after_any_single_input_change(change):
    approved_note = "approved note"
    approved_source_hash = "source-v1"
    approved_model_digest = "model-v1"
    current_source_hash = approved_source_hash
    current_model_digest = approved_model_digest
    regenerated_note = approved_note
    if change == "source":
        current_source_hash = "source-v2"
    elif change == "model":
        current_model_digest = "model-v2"
    else:
        regenerated_note = "changed note"

    result = replay(
        approved_note=approved_note,
        approved_source_hash=approved_source_hash,
        approved_model_digest=approved_model_digest,
        current_source_hash=current_source_hash,
        current_model_digest=current_model_digest,
        regenerated_note=regenerated_note,
    )
    assert result["approval_stale"] is True
    assert result["publication_allowed"] is False


def test_replay_keeps_unchanged_approval_stale_safe_without_marking_stale():
    result = replay(
        approved_note="approved note",
        approved_source_hash="source-v1",
        approved_model_digest="model-v1",
        current_source_hash="source-v1",
        current_model_digest="model-v1",
        regenerated_note="approved note",
    )
    assert not result["source_changed"]
    assert not result["model_changed"]
    assert not result["note_changed"]
    assert result["approval_stale"] is False
    assert result["publication_allowed"] is False
