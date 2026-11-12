from services.evidence_graph import build


def test_evidence_graph_connects_audio_to_export():
    result = build(
        audio_id="a",
        transcript_segment_id="s",
        evidence_span="span:1-5",
        fact_id="f",
        note_statement_id="n",
        export_id="x",
    )
    assert len(result["edges"]) == 5
    assert result["edges"][0]["type"] == "audio_to_transcript"
    assert result["clinical_release_authorized"] is False
