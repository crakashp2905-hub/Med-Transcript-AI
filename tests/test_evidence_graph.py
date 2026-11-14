import pytest
import random

from services.canonical import content_sha256
from services.evidence_graph import (
    build,
    validate_approved_export,
    validate_graph_invariants,
    validate_proposal,
)


def test_evidence_graph_invariants_reject_missing_nodes_cycles_and_tenants():
    nodes = ["audio", "segment", "span", "fact"]
    edges = [
        {"from": "audio", "to": "segment", "type": "audio_to_transcript"},
        {"from": "segment", "to": "span", "type": "transcript_to_span"},
        {"from": "span", "to": "fact", "type": "span_to_fact"},
    ]
    assert validate_graph_invariants(edges, nodes)["acyclic"] is True

    with pytest.raises(ValueError, match="evidence_graph_edge_node_missing"):
        validate_graph_invariants(
            [*edges, {"from": "fact", "to": "missing", "type": "x"}], nodes
        )
    with pytest.raises(ValueError, match="evidence_graph_cycle_detected"):
        validate_graph_invariants(
            [*edges, {"from": "fact", "to": "audio", "type": "cycle"}], nodes
        )
    with pytest.raises(ValueError, match="evidence_graph_cross_tenant_edge"):
        validate_graph_invariants(
            edges,
            nodes,
            tenant_by_node={
                "audio": "tenant-a",
                "segment": "tenant-b",
                "span": "tenant-a",
                "fact": "tenant-a",
            },
        )


def test_seeded_graph_fuzz_preserves_dag_and_rejects_back_edges():
    rng = random.Random(1907)
    for _ in range(64):
        nodes = [f"node-{index}" for index in range(6)]
        edges = [
            {"from": nodes[index], "to": nodes[index + 1], "type": "chain"}
            for index in range(len(nodes) - 1)
        ]
        edges.extend(
            {"from": nodes[left], "to": nodes[right], "type": "fuzz"}
            for left in range(len(nodes))
            for right in range(left + 1, len(nodes))
            if right != left + 1 and rng.random() < 0.25
        )
        validate_graph_invariants(edges, nodes)
        # Connect the final node back to the first; all generated nodes remain
        # reachable in the graph shape, and the cycle must always be rejected.
        cyclic = [*edges, {"from": nodes[-1], "to": nodes[0], "type": "tamper"}]
        with pytest.raises(ValueError, match="evidence_graph_cycle_detected"):
            validate_graph_invariants(cyclic, nodes)


def test_proposal_rejects_audio_segment_identity_collision_as_cycle():
    transcript = {
        "id": "transcript-v1",
        "audio_asset_id": "shared-id",
        "segments": [{"segment_id": "shared-id", "text": "No fever."}],
    }
    fact = {
        "fact_id": "fact-1",
        "evidence": {
            "segment_id": "shared-id",
            "start_char": 0,
            "end_char": 9,
            "quote": "No fever.",
        },
    }
    with pytest.raises(ValueError, match="evidence_graph_cycle_detected"):
        validate_proposal(transcript, [fact])


def test_multiple_facts_in_one_segment_share_edges_and_keep_fact_links():
    transcript = {
        "id": "transcript-v1",
        "audio_asset_id": "audio-1",
        "segments": [{"segment_id": "segment-1", "text": "Cough; no fever."}],
    }
    facts = [
        {
            "fact_id": "fact-cough",
            "evidence": {
                "segment_id": "segment-1",
                "start_char": 0,
                "end_char": 5,
                "quote": "Cough",
            },
        },
        {
            "fact_id": "fact-fever",
            "evidence": {
                "segment_id": "segment-1",
                "start_char": 7,
                "end_char": 16,
                "quote": "no fever.",
            },
        },
    ]

    result = validate_proposal(transcript, facts)

    assert sum(edge["type"] == "audio_to_transcript" for edge in result["edges"]) == 1
    assert sum(edge["type"] == "transcript_to_span" for edge in result["edges"]) == 2
    assert {
        edge["to"] for edge in result["edges"] if edge["type"] == "span_to_fact"
    } == {"fact-cough", "fact-fever"}


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
            {
                "fact_id": "fact-manual",
                "origin": "manual_no_audio_evidence",
                "source_modality": "manual_no_audio_evidence",
                "owner_clinician_id": "clinician-1",
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
                    {
                        "statement_id": "statement-manual",
                        "fact_ids": ["fact-manual"],
                        "origin": "manual_no_audio_evidence",
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
    assert edge_types.count("fact_to_note") == 3
    assert edge_types.count("note_to_export") == 3
    assert graph["hashes"]["audio_sha256"] == "a" * 64
    assert graph["hashes"]["note_sha256"] == note_sha256
    assert graph["hashes"]["export_artifact_sha256"] == "b" * 64
    assert graph["clinician_entered_fact_ids"] == ["fact-clinician"]
    assert graph["manual_no_audio_evidence_fact_ids"] == ["fact-manual"]
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


def test_amended_export_graph_binds_parent_note_hash_and_amendment_reason():
    transcript = {
        "id": "transcript-v1",
        "encounter_id": "encounter-1",
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
    fact = {
        "fact_id": "fact-1",
        "origin": "source_linked",
        "evidence": evidence,
        "excluded": False,
    }
    statement = {
        "statement_id": "statement-1",
        "fact_ids": ["fact-1"],
        "origin": "source_linked",
        "source_version_id": transcript["id"],
        "evidence": evidence,
    }
    parent_note = {
        "id": "note-v1",
        "version": 1,
        "encounter_id": "encounter-1",
        "parent_version_id": None,
        "transcript_version_id": transcript["id"],
        "transcript_sha256": content_sha256(transcript),
        "amendment_reason": "",
        "facts": [fact],
        "sections": [{"key": "subjective", "statements": [statement]}],
    }
    parent_sha256 = content_sha256(parent_note)
    amended_note = {
        **parent_note,
        "id": "note-v2",
        "version": 2,
        "parent_version_id": parent_note["id"],
        "amendment_reason": "Correct the source-linked symptom statement.",
    }
    note_sha256 = content_sha256(amended_note)
    transcript_sha256 = content_sha256(transcript)
    approval = {
        "id": "approval-v2",
        "note_version_id": amended_note["id"],
        "note_sha256": note_sha256,
        "transcript_version_id": transcript["id"],
        "transcript_sha256": transcript_sha256,
    }

    graph = validate_approved_export(
        transcript=transcript,
        transcript_sha256=transcript_sha256,
        note=amended_note,
        note_sha256=note_sha256,
        approval=approval,
        export_id="export-v2",
        artifact_sha256="b" * 64,
        amendment_parent=parent_note,
        amendment_parent_sha256=parent_sha256,
    )

    assert {
        "from": "note-v1",
        "to": "note-v2",
        "type": "parent_note_to_amendment",
    } in graph["edges"]
    assert graph["amendment"]["parent_note_sha256"] == parent_sha256
    assert graph["amendment"]["reason_sha256"] == content_sha256(
        {"reason": amended_note["amendment_reason"]}
    )
    assert graph["hashes"]["note_sha256"] == note_sha256
    assert graph["complete_to_export"] is True

    with pytest.raises(ValueError, match="evidence_graph_amendment_parent_invalid"):
        validate_approved_export(
            transcript=transcript,
            transcript_sha256=transcript_sha256,
            note=amended_note,
            note_sha256=note_sha256,
            approval=approval,
            export_id="export-v2",
            artifact_sha256="b" * 64,
            amendment_parent=parent_note,
            amendment_parent_sha256="c" * 64,
        )
