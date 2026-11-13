import pytest

from services.asr.preview_divergence import compare_preview_to_final


def _preview(**overrides):
    result = {
        "status": "provisional_not_a_source_version",
        "approvable": False,
        "profile_sha256": "a" * 64,
        "input_sha256": "b" * 64,
        "provisional_segments": [{"text": "Take two tablets daily."}],
    }
    return result | overrides


def _final(**overrides):
    result = {
        "transcript_version_id": "transcript-1",
        "profile_sha256": "a" * 64,
        "segments": [{"text": "Take 2 tablets daily."}],
    }
    return result | overrides


def test_preview_final_divergence_is_diagnostic_and_does_not_approve():
    report = compare_preview_to_final(_preview(), _final())
    assert report["kind"] == "preview_final_divergence"
    assert report["diagnostic_only"] is True
    assert report["approvable"] is False
    assert report["word_edit_count"] == 1
    assert report["normalized_word_divergence"] == 0.25


@pytest.mark.parametrize(
    ("preview", "final", "error"),
    [
        (_preview(status="succeeded"), _final(), "preview_result_not_provisional"),
        (_preview(approvable=True), _final(), "preview_must_be_unapprovable"),
        (_preview(), _final(profile_sha256="c" * 64), "profile_mismatch"),
        (_preview(), _final(transcript_version_id=None), "final_transcript_version_required"),
    ],
)
def test_preview_divergence_rejects_unpaired_or_unsafe_inputs(preview, final, error):
    with pytest.raises(ValueError, match=error):
        compare_preview_to_final(preview, final)
