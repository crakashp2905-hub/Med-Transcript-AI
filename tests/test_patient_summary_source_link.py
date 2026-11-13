from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_alternate_summary_retains_each_claims_evidence_and_caveats():
    component = (ROOT / "apps/clinician-web/src/PresentationTools.tsx").read_text(
        encoding="utf-8"
    )
    screen = (ROOT / "apps/clinician-web/src/screens/NoteReviewScreen.tsx").read_text(
        encoding="utf-8"
    )

    assert "subject: ${fact.subject}" in component
    assert "assertion: ${fact.assertion}" in component
    assert "time: ${fact.temporality}" in component
    assert "Source turn ${ordinal.get(segment.segment_id)}" in component
    assert "${fact.evidence!.quote}" in component
    assert "not a negative finding" in component
    assert "untranscribed audio interval(s) remain" in component
    assert "sourceTranscriptId===note.transcript_version_id" in component
    assert "readOnly disabled={!eligible}" in component
    assert "sourceReviewFlags={sourceForNote?.review_flags||[]}" in screen

