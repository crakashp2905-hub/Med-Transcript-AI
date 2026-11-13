import hashlib

import pytest

from services.review.engine import render_export


def test_text_exports_cite_exact_source_spans_and_flag_clinician_additions():
    quote = "Patient reports cough."
    note = {
        "id": "note-v1",
        "encounter_id": "encounter-v1",
        "version": 1,
        "sections": [
            {
                "key": "subjective",
                "statements": [
                    {
                        "text": quote,
                        "origin": "source_linked",
                        "source_version_id": "transcript-v1",
                        "evidence": {
                            "segment_id": "segment-v1",
                            "start_char": 0,
                            "end_char": len(quote),
                            "quote": quote,
                        },
                    },
                    {
                        "text": "Patient confirms an additional concern.",
                        "origin": "clinician_entered",
                        "source_version_id": None,
                        "evidence": None,
                    },
                    {
                        "text": "Clinician confirms prior dose by label.",
                        "origin": "manual_no_audio_evidence",
                        "owner_clinician_id": "clinician-1",
                        "source_version_id": None,
                        "evidence": None,
                    },
                ],
            }
        ],
    }
    approval = {
        "approved_at": "2026-11-12T00:00:00+00:00",
        "note_sha256": "a" * 64,
    }

    output = render_export(note, approval, "text")

    quote_hash = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    assert (
        f"[Source: transcript transcript-v1; segment segment-v1; characters 0-{len(quote)}; "
        f"quote SHA-256 {quote_hash}.]"
    ) in output
    assert "[Clinician-entered addition; not audio-derived.]" in output
    assert (
        "[Clinician-entered addition; source: no audio evidence; owner clinician: clinician-1.]"
        in output
    )


@pytest.mark.parametrize(
    "statement, message",
    [
        (
            {"text": "Unsupported", "origin": "source_linked", "evidence": None},
            "approved_statement_source_missing",
        ),
        (
            {
                "text": "Unsupported",
                "origin": "clinician_entered",
                "evidence": {"quote": "unsupported"},
            },
            "clinician_statement_cannot_claim_source_evidence",
        ),
        (
            {"text": "Unsupported", "origin": "unattributed", "evidence": None},
            "approved_statement_origin_missing",
        ),
    ],
)
def test_text_exports_reject_missing_or_fabricated_statement_attribution(
    statement, message
):
    note = {
        "id": "note-v1",
        "encounter_id": "encounter-v1",
        "version": 1,
        "sections": [{"key": "subjective", "statements": [statement]}],
    }
    approval = {
        "approved_at": "2026-11-12T00:00:00+00:00",
        "note_sha256": "a" * 64,
    }
    with pytest.raises(ValueError, match=message):
        render_export(note, approval, "text")
