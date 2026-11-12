import copy

import pytest

from services.asr.removal_propagation import (
    rebuild_after_revocation,
    source_reference_id,
)


def _source(record_id, reference_sha256):
    return {
        "dataset_id": "synthetic-development",
        "record_id": record_id,
        "reference_sha256": reference_sha256,
    }


def test_revocation_removes_lexicon_and_retraining_lineage_without_mutating_inputs():
    revoked_row = _source("correction-01", "a" * 64)
    retained_row = _source("correction-02", "b" * 64)
    revoked_id = source_reference_id(**revoked_row)
    retained_id = source_reference_id(**retained_row)
    lexicon = {
        "candidate_terms": ["warfarin", "metformin"],
        "entries": [
            {
                "term": "warfarin",
                "provenance": [revoked_row, retained_row],
            },
            {"term": "metformin", "provenance": [revoked_row]},
        ],
    }
    manifest = {
        "records": [
            {"record_id": "train-01", "source_ids": [revoked_id]},
            {"record_id": "train-02", "source_ids": [retained_id]},
        ],
        "artifacts": [
            {
                "artifact_id": "adapter-v1",
                "source_ids": [revoked_id, retained_id],
            },
            {"artifact_id": "adapter-clean", "source_ids": [retained_id]},
        ],
    }
    original_lexicon = copy.deepcopy(lexicon)
    original_manifest = copy.deepcopy(manifest)

    result = rebuild_after_revocation(
        lexicon=lexicon,
        retraining_manifest=manifest,
        revoked_source_ids=[revoked_id],
    )

    assert lexicon == original_lexicon
    assert manifest == original_manifest
    assert result["removed_lexicon_occurrences"] == 2
    assert result["removed_lexicon_terms"] == 1
    assert result["removed_training_records"] == 1
    assert result["invalidated_artifact_ids"] == ["adapter-v1"]
    assert result["retraining_required"] is True
    assert result["learned_weights_erased"] is False
    assert result["revoked_sources_referenced"] is False
    assert result["rebuilt_lexicon"]["candidate_terms"] == ["warfarin"]
    assert result["rebuilt_manifest"]["records"] == [
        {"record_id": "train-02", "source_ids": [retained_id]}
    ]
    assert result["rebuilt_manifest"]["artifacts"] == [
        {"artifact_id": "adapter-clean", "source_ids": [retained_id]}
    ]
    assert revoked_id not in repr(result["rebuilt_lexicon"])
    assert revoked_id not in repr(result["rebuilt_manifest"])


def test_revocation_fails_closed_on_empty_or_malformed_lineage():
    with pytest.raises(ValueError, match="revocation_set_empty"):
        rebuild_after_revocation(
            lexicon={"entries": []},
            retraining_manifest={"records": []},
            revoked_source_ids=[],
        )
    with pytest.raises(ValueError, match="source_lineage_invalid"):
        rebuild_after_revocation(
            lexicon={"entries": []},
            retraining_manifest={"records": [{"source_ids": ["bad"]}]},
            revoked_source_ids=["0" * 64],
        )
