"""Deterministic scoring of note claims against typed, cited source facts."""

import json


CRITICAL_FIELDS = {
    "subject",
    "assertion",
    "temporality",
    "dose",
    "unit",
    "route",
    "frequency",
    "duration",
}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def score_grounded_draft(source_facts, note_claims):
    """Score exact supported claims and material-source recall.

    Expected rows are ``{id, fact, material?}``; claims are
    ``{fact, source_fact_ids}``. Claims have no authority to modify approval.
    """
    if not isinstance(source_facts, list) or not isinstance(note_claims, list):
        raise ValueError("draft_grounding_inputs_must_be_lists")
    sources = {}
    for row in source_facts:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"]
            or not isinstance(row.get("fact"), dict)
            or row["id"] in sources
        ):
            raise ValueError("draft_source_fact_invalid")
        sources[row["id"]] = row
    supported = unsupported = dangerous = malformed_citations = 0
    supported_material_ids = set()
    for claim in note_claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("fact"), dict):
            raise ValueError("draft_note_claim_invalid")
        citations = claim.get("source_fact_ids")
        if not isinstance(citations, list) or any(
            not isinstance(item, str) for item in citations
        ):
            raise ValueError("draft_claim_evidence_references_invalid")
        cited = [sources[item] for item in citations if item in sources]
        if len(cited) != len(citations):
            malformed_citations += 1
        exact = [
            row for row in cited if _canonical(row["fact"]) == _canonical(claim["fact"])
        ]
        if exact:
            supported += 1
            supported_material_ids.update(
                row["id"] for row in exact if row.get("material") is True
            )
            continue
        unsupported += 1
        for row in cited:
            source = row["fact"]
            note = claim["fact"]
            same_identity = all(
                source.get(key) == note.get(key)
                for key in ("category", "concept")
                if key in source or key in note
            )
            if same_identity and any(
                source.get(key) != note.get(key) for key in CRITICAL_FIELDS
            ):
                dangerous += 1
                break
    material_ids = {
        row["id"] for row in sources.values() if row.get("material") is True
    }
    return {
        "schema_version": "grounded_draft_metrics_v1",
        "note_claim_count": len(note_claims),
        "supported_claim_count": supported,
        "unsupported_claim_count": unsupported,
        "malformed_or_unknown_citation_claim_count": malformed_citations,
        "factual_precision": supported / len(note_claims) if note_claims else None,
        "material_source_fact_count": len(material_ids),
        "material_source_facts_covered": len(supported_material_ids),
        "material_source_recall": len(supported_material_ids) / len(material_ids)
        if material_ids
        else None,
        "dangerous_transformation_count": dangerous,
        "approval_effect": "none",
        "clinical_accuracy_claim": False,
    }
