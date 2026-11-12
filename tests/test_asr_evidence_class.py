from services.asr.provenance import (
    MEASURED_TRANSCRIPTION_QUALITY,
    REAL_MODEL_INFERENCE,
    SOFTWARE_TRANSPORT_TEST,
    evaluation_evidence_class,
    execution_mode,
    is_quality_evidence,
)


def test_transcript_replay_remains_software_transport_evidence():
    raw = {
        "provider_mode": "synthetic_fixture",
        "inference_executed": False,
        "segments": [{"text": "Plausible transcript text"}],
    }
    mode = execution_mode(raw)

    assert mode != REAL_MODEL_INFERENCE
    assert (
        evaluation_evidence_class([{"status": "completed", "inference_mode": mode}])
        == SOFTWARE_TRANSPORT_TEST
    )


def test_actual_model_inference_is_quality_evidence():
    report = {
        "evidence_class": MEASURED_TRANSCRIPTION_QUALITY,
        "samples": [{"inference_mode": REAL_MODEL_INFERENCE}],
    }

    assert (
        evaluation_evidence_class(report["samples"]) == MEASURED_TRANSCRIPTION_QUALITY
    )
    assert is_quality_evidence(report)


def test_legacy_quality_report_needs_model_runtime_and_all_hypotheses():
    legacy = {
        "profile_id": "historic-model",
        "model_revision": "b" * 40,
        "profile_sha256": "a" * 64,
        "sample_count": 1,
        "samples": [
            {
                "sample_id": "sample-1",
                "status": "completed",
                "reference_words": 4,
                "normalized_edits": 1,
            }
        ],
    }
    assert is_quality_evidence(legacy)
    legacy.pop("profile_sha256")
    assert not is_quality_evidence(legacy)
