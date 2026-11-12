import json

import pytest

from services.asr.candidate_receipt import (
    create_candidate_receipt,
    write_candidate_receipt,
)


def candidate(candidate_id, text):
    return {
        "candidate_id": candidate_id,
        "text": text,
        "backend_id": "local-asr",
        "profile_sha256": "a" * 64,
        "decoder_config_sha256": "b" * 64,
    }


def receipt(**changes):
    arguments = {
        "audio_asset_id": "audio-asset-1",
        "audio_sha256": "c" * 64,
        "start_ms": 1200,
        "end_ms": 3400,
        "source_transcript_version": "transcript-v2",
        "source_transcript_sha256": "d" * 64,
        "original_hypothesis": candidate("original", "No allergy."),
        "alternatives": [candidate("alternative-1", "Penicillin allergy.")],
        "selection_policy_id": "risk_selective_v1",
        "selection_policy_version": "1.0.0",
        "abstained": True,
        "abstention_reason": "negation_conflict_requires_review",
    }
    arguments.update(changes)
    return create_candidate_receipt(**arguments)


def test_candidate_receipt_is_source_bound_and_keeps_abstention_and_alternatives():
    result = receipt()
    assert result["audio_asset_id"] == "audio-asset-1"
    assert result["original_hypothesis"]["text"] == "No allergy."
    assert result["alternatives"][0]["text"] == "Penicillin allergy."
    assert result["selection_policy"]["version"] == "1.0.0"
    assert result["abstained"] is True and result["selected_candidate_id"] is None
    assert result["review_required"] is True and result["adopted"] is False
    assert result["clinical_truth_verified"] is False


def test_receipt_digest_is_deterministic_and_write_once(tmp_path):
    first = receipt()
    assert first["receipt_sha256"] == receipt()["receipt_sha256"]
    path = tmp_path / "candidate.json"
    write_candidate_receipt(path, first)
    assert (
        json.loads(path.read_text(encoding="utf-8"))["receipt_sha256"]
        == first["receipt_sha256"]
    )
    with pytest.raises(FileExistsError):
        write_candidate_receipt(path, first)


def test_receipt_rejects_invalid_abstention_and_reference_text_fields():
    with pytest.raises(ValueError, match="abstention_requires_reason"):
        receipt(selected_candidate_id="original")
    with pytest.raises(ValueError, match="candidate_fields_invalid"):
        receipt(
            original_hypothesis={**candidate("original", "ok"), "reference": "gold"}
        )
