import pytest

from services.canonical import content_sha256
from services.evidence_graph import build, validate_approved_export


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


def test_approved_export_graph_extends_exact_hash_chain_to_note_and_export():
    transcript = {
        "id": "transcript-v1",
        "audio_asset_id": "audio-1",
        "input_sha256": "a" * 64,
        "segments": [{"segment_id": "segment-1", "text": "Patient reports cough."}],
    }
    evidence = {
        "segment_id": "segment-1",
        "start_char": 0,
        "end_char": 22,
        "quote": "Patient reports cough.",
    }
    note = {
        "id": "note-v1",
        "transcript_version_id": transcript["id"],
        "transcript_sha256": content_sha256(transcript),
        "facts": [
            {
                "fact_id": "fact-source",
                "origin": "source_linked",
                "evidence": evidence,
                "excluded": False,
            },
            {
                "fact_id": "fact-clinician",
                "origin": "clinician_entered",
                "evidence": None,
                "excluded": False,
            },
        ],
        "sections": [
            {
                "key": "subjective",
                "statements": [
                    {
                        "statement_id": "statement-source",
                        "fact_ids": ["fact-source"],
                        "origin": "source_linked",
                        "source_version_id": transcript["id"],
                        "evidence": evidence,
                    },
                    {
                        "statement_id": "statement-clinician",
                        "fact_ids": ["fact-clinician"],
                        "origin": "clinician_entered",
                        "source_version_id": None,
                        "evidence": None,
                    },
                ],
            }
        ],
    }
    note_sha256 = content_sha256(note)
    approval = {
        "id": "approval-v1",
        "note_version_id": note["id"],
        "note_sha256": note_sha256,
        "transcript_version_id": transcript["id"],
        "transcript_sha256": content_sha256(transcript),
    }

    graph = validate_approved_export(
        transcript=transcript,
        transcript_sha256=content_sha256(transcript),
        note=note,
        note_sha256=note_sha256,
        approval=approval,
        export_id="export-v1",
        artifact_sha256="b" * 64,
    )
    edge_types = [edge["type"] for edge in graph["edges"]]
    assert edge_types.count("fact_to_note") == 2
    assert edge_types.count("note_to_export") == 2
    assert graph["hashes"]["audio_sha256"] == "a" * 64
    assert graph["hashes"]["note_sha256"] == note_sha256
    assert graph["hashes"]["export_artifact_sha256"] == "b" * 64
    assert graph["clinician_entered_fact_ids"] == ["fact-clinician"]
    assert graph["complete_to_export"] is True
    assert graph["clinical_release_authorized"] is False


def test_approved_export_graph_rejects_hash_chain_and_source_mismatches():
    transcript = {
        "id": "transcript-v1",
        "audio_asset_id": "audio-1",
        "input_sha256": "a" * 64,
        "segments": [{"segment_id": "segment-1", "text": "Cough"}],
    }
    evidence = {
        "segment_id": "segment-1",
        "start_char": 0,
        "end_char": 5,
        "quote": "Cough",
    }
    note = {
        "id": "note-v1",
        "transcript_version_id": transcript["id"],
        "transcript_sha256": content_sha256(transcript),
        "facts": [
            {
                "fact_id": "fact-1",
                "origin": "source_linked",
                "evidence": evidence,
                "excluded": False,
            }
        ],
        "sections": [
            {
                "key": "subjective",
                "statements": [
                    {
                        "statement_id": "statement-1",
                        "fact_ids": ["fact-1"],
                        "origin": "source_linked",
                        "source_version_id": transcript["id"],
                        "evidence": evidence,
                    }
                ],
            }
        ],
    }
    note_sha256 = content_sha256(note)
    approval = {
        "id": "approval-v1",
        "note_version_id": note["id"],
        "note_sha256": note_sha256,
        "transcript_version_id": transcript["id"],
        "transcript_sha256": content_sha256(transcript),
    }
    args = {
        "transcript": transcript,
        "transcript_sha256": content_sha256(transcript),
        "note": note,
        "note_sha256": note_sha256,
        "approval": approval,
        "export_id": "export-v1",
        "artifact_sha256": "b" * 64,
    }
    with pytest.raises(ValueError, match="evidence_graph_hash_chain_invalid"):
        validate_approved_export(**{**args, "note_sha256": "c" * 64})

    changed_note = {**note, "transcript_version_id": "transcript-v2"}
    with pytest.raises(ValueError, match="evidence_graph_hash_chain_invalid"):
        validate_approved_export(
            **{
                **args,
                "note": changed_note,
                "note_sha256": content_sha256(changed_note),
            }
        )
