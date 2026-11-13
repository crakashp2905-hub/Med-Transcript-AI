"""Explicit source-to-export evidence graph links."""

from collections import defaultdict, deque

from services.canonical import content_sha256


def validate_graph_invariants(edges, node_ids, *, tenant_by_node=None):
    """Reject malformed, cyclic, or cross-tenant evidence edge sets."""
    nodes = set(node_ids)
    if len(nodes) != len(node_ids) or not nodes:
        raise ValueError("evidence_graph_nodes_invalid")
    adjacency = defaultdict(list)
    indegree = dict.fromkeys(nodes, 0)
    seen = set()
    for edge in edges:
        source, target = edge.get("from"), edge.get("to")
        edge_type = edge.get("type")
        if (
            not source
            or not target
            or source not in nodes
            or target not in nodes
            or not edge_type
        ):
            raise ValueError("evidence_graph_edge_node_missing")
        key = (source, target, edge_type)
        if key in seen:
            raise ValueError("evidence_graph_edge_duplicate")
        seen.add(key)
        if tenant_by_node is not None:
            if source not in tenant_by_node or target not in tenant_by_node:
                raise ValueError("evidence_graph_tenant_missing")
            if tenant_by_node[source] != tenant_by_node[target]:
                raise ValueError("evidence_graph_cross_tenant_edge")
        adjacency[source].append(target)
        indegree[target] += 1
    queue = deque(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for target in adjacency[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        raise ValueError("evidence_graph_cycle_detected")
    return {"nodes": len(nodes), "edges": len(edges), "acyclic": True}


def validate_proposal(transcript, facts):
    """Resolve real source IDs and exact quotes before building proposal edges."""
    audio_id = transcript.get("audio_asset_id")
    if not audio_id or not transcript.get("id"):
        raise ValueError("evidence_graph_source_required")
    segments = {s["segment_id"]: s for s in transcript["segments"]}
    if len(segments) != len(transcript["segments"]):
        raise ValueError("evidence_graph_duplicate_segment")
    edges, seen = [], set()
    for fact in facts:
        fid = fact.get("fact_id")
        evidence = fact.get("evidence") or {}
        segment = segments.get(evidence.get("segment_id"))
        start, end = evidence.get("start_char"), evidence.get("end_char")
        if (
            not fid
            or fid in seen
            or segment is None
            or type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(segment["text"])
            or segment["text"][start:end] != evidence.get("quote")
        ):
            raise ValueError("evidence_graph_invalid_source_link")
        seen.add(fid)
        span_id = content_sha256({"transcript": transcript["id"], "evidence": evidence})
        edges.extend(
            [
                {
                    "from": str(audio_id),
                    "to": segment["segment_id"],
                    "type": "audio_to_transcript",
                },
                {
                    "from": segment["segment_id"],
                    "to": span_id,
                    "type": "transcript_to_span",
                },
                {"from": span_id, "to": fid, "type": "span_to_fact"},
            ]
        )
    node_ids = {str(audio_id)}
    node_ids.update(str(segment_id) for segment_id in segments)
    node_ids.update(edge["from"] for edge in edges)
    node_ids.update(edge["to"] for edge in edges)
    validate_graph_invariants(edges, list(node_ids))
    return {
        "edges": edges,
        "transcript_version_id": transcript["id"],
        "source_sha256": content_sha256(transcript),
        "facts_checked": len(facts),
        "complete_to_fact": True,
        "complete_to_export": False,
        "clinical_release_authorized": False,
    }


def build(
    *,
    audio_id,
    transcript_segment_id,
    evidence_span,
    fact_id,
    note_statement_id,
    export_id,
):
    values = (
        audio_id,
        transcript_segment_id,
        evidence_span,
        fact_id,
        note_statement_id,
        export_id,
    )
    if any(not value for value in values):
        raise ValueError("evidence_graph_link_required")
    edges = [
        {
            "from": audio_id,
            "to": transcript_segment_id,
            "type": "audio_to_transcript",
        },
        {
            "from": transcript_segment_id,
            "to": evidence_span,
            "type": "transcript_to_span",
        },
        {"from": evidence_span, "to": fact_id, "type": "span_to_fact"},
        {"from": fact_id, "to": note_statement_id, "type": "fact_to_note"},
        {"from": note_statement_id, "to": export_id, "type": "note_to_export"},
    ]
    validate_graph_invariants(
        edges,
        list({edge["from"] for edge in edges} | {edge["to"] for edge in edges}),
    )
    return {
        "edges": edges,
        "complete": True,
        "clinical_release_authorized": False,
    }


def validate_approved_export(
    *,
    transcript,
    transcript_sha256,
    note,
    note_sha256,
    approval,
    export_id,
    artifact_sha256,
):
    """Validate source→fact→note→export edges and their immutable hash chain."""
    if (
        content_sha256(transcript) != transcript_sha256
        or transcript.get("input_sha256") is None
        or note.get("transcript_version_id") != transcript.get("id")
        or note.get("transcript_sha256") != transcript_sha256
        or content_sha256(note) != note_sha256
        or approval.get("note_version_id") != note.get("id")
        or approval.get("note_sha256") != note_sha256
        or approval.get("transcript_version_id") != transcript.get("id")
        or approval.get("transcript_sha256") != transcript_sha256
        or not export_id
        or not artifact_sha256
    ):
        raise ValueError("evidence_graph_hash_chain_invalid")

    facts = {str(fact.get("fact_id")): fact for fact in note.get("facts", [])}
    if len(facts) != len(note.get("facts", [])):
        raise ValueError("evidence_graph_duplicate_fact")
    source_facts = [
        fact for fact in facts.values() if fact.get("origin") == "source_linked"
    ]
    graph = validate_proposal(transcript, source_facts)
    edges = list(graph["edges"])
    seen_facts = set()
    clinician_entered_fact_ids = []
    manual_no_audio_evidence_fact_ids = []
    for section in note.get("sections", []):
        for statement in section.get("statements", []):
            statement_id = str(statement.get("statement_id", ""))
            fact_ids = [str(value) for value in statement.get("fact_ids", [])]
            if (
                not statement_id
                or not fact_ids
                or any(value not in facts for value in fact_ids)
            ):
                raise ValueError("evidence_graph_note_fact_link_invalid")
            origins = {facts[value].get("origin") for value in fact_ids}
            if len(origins) != 1 or statement.get("origin") not in origins:
                raise ValueError("evidence_graph_note_origin_invalid")
            origin = next(iter(origins))
            if origin == "source_linked":
                if statement.get("source_version_id") != transcript.get("id"):
                    raise ValueError("evidence_graph_note_source_invalid")
                evidence = statement.get("evidence")
                if not evidence or any(
                    facts[value].get("evidence") != evidence for value in fact_ids
                ):
                    raise ValueError("evidence_graph_note_evidence_invalid")
                span_id = content_sha256(
                    {"transcript": transcript["id"], "evidence": evidence}
                )
                edges.extend(
                    {"from": value, "to": statement_id, "type": "fact_to_note"}
                    for value in fact_ids
                )
                if not any(
                    edge["from"] == span_id
                    and edge["to"] == value
                    and edge["type"] == "span_to_fact"
                    for value in fact_ids
                    for edge in graph["edges"]
                ):
                    raise ValueError("evidence_graph_source_fact_edge_missing")
            elif origin in {"clinician_entered", "manual_no_audio_evidence"}:
                if statement.get("evidence") is not None:
                    raise ValueError("evidence_graph_clinician_citation_invalid")
                if origin == "manual_no_audio_evidence":
                    if any(
                        not facts[value].get("owner_clinician_id")
                        or facts[value].get("source_modality")
                        != "manual_no_audio_evidence"
                        for value in fact_ids
                    ):
                        raise ValueError("evidence_graph_manual_owner_missing")
                    manual_no_audio_evidence_fact_ids.extend(fact_ids)
                else:
                    clinician_entered_fact_ids.extend(fact_ids)
                edges.extend(
                    {"from": value, "to": statement_id, "type": "fact_to_note"}
                    for value in fact_ids
                )
            else:
                raise ValueError("evidence_graph_note_origin_invalid")
            seen_facts.update(fact_ids)
            edges.append(
                {"from": statement_id, "to": str(export_id), "type": "note_to_export"}
            )

    required_facts = {
        fact_id for fact_id, fact in facts.items() if not fact.get("excluded", False)
    }
    if not required_facts <= seen_facts:
        raise ValueError("evidence_graph_note_coverage_incomplete")

    validate_graph_invariants(
        edges,
        list({edge["from"] for edge in edges} | {edge["to"] for edge in edges}),
    )
    payload = {
        "edges": edges,
        "hashes": {
            "audio_sha256": transcript["input_sha256"],
            "transcript_sha256": transcript_sha256,
            "note_sha256": note_sha256,
            "approval_note_sha256": approval["note_sha256"],
            "export_artifact_sha256": artifact_sha256,
        },
        "transcript_version_id": transcript["id"],
        "note_version_id": note["id"],
        "approval_id": approval["id"],
        "export_id": str(export_id),
        "clinician_entered_fact_ids": sorted(set(clinician_entered_fact_ids)),
        "manual_no_audio_evidence_fact_ids": sorted(
            set(manual_no_audio_evidence_fact_ids)
        ),
        "complete_to_export": True,
        "clinical_release_authorized": False,
    }
    return {**payload, "graph_sha256": content_sha256(payload)}
