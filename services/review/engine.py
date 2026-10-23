"""Evidence validation and bounded clinician-reviewed template drafting; no diagnostic model."""

import re
from uuid import uuid4

from fastapi import HTTPException


AMBIGUITY = re.compile(r"\b(?:unclear|inaudible|maybe|unsure|not sure)\b|\d+(?:\.\d+)?\s*(?:or|/)\s*\d+", re.I)
CRITICAL = re.compile(r"\b(?:mg|mcg|ml|units|insulin|allerg\w*|metformin|warfarin|dose|dosage)\b|\d", re.I)


def validate_evidence(facts, transcript):
    segments = {row["segment_id"]: row for row in transcript["segments"]}
    seen = set()
    for fact in facts:
        if fact.fact_id in seen:
            raise HTTPException(422, "duplicate_fact_id")
        seen.add(fact.fact_id)
        if fact.origin == "source_linked":
            evidence = fact.evidence
            segment = segments.get(str(evidence.segment_id))
            if (not segment or evidence.end_char <= evidence.start_char or evidence.end_char > len(segment["text"])
                    or segment["text"][evidence.start_char:evidence.end_char] != evidence.quote):
                raise HTTPException(422, "invalid_evidence_reference")


def propose_facts(transcript):
    result = []
    for segment in transcript["segments"]:
        if not segment["text"].strip():
            continue
        result.append({"fact_id": str(uuid4()), "category": "other", "section": "subjective",
            "text": segment["text"], "subject": "unknown", "assertion": "uncertain", "temporality": "unknown",
            "origin": "source_linked", "reviewed": False, "critical_reviewed": False, "clarification": "",
            "evidence": {"segment_id": segment["segment_id"], "start_char": 0,
                         "end_char": len(segment["text"]), "quote": segment["text"]}})
    return result


def findings_for(note, transcript):
    findings = []
    def add(code, message, fact_id=None, severity="major"):
        findings.append({"finding_id": str(uuid4()), "code": code, "message": message,
                         "severity": severity, "fact_id": fact_id, "state": "open", "blocks_approval": True})
    review = transcript.get("review", {})
    if not review.get("english_confirmed"):
        add("language_support_unverified", "Confirm supported English against the original source.")
    if not review.get("source_completeness_reviewed") or len(review.get("source_review_reason", "").strip()) < 10:
        add("source_review_required", "Review the complete source, including untranscribed intervals.")
    if any(row.get("role") == "unknown" and row["text"].strip() for row in transcript["segments"]):
        add("speaker_roles_unconfirmed", "Confirm source speaker roles before attribution.")
    for fact in note["facts"]:
        fid = fact["fact_id"]
        if not fact["reviewed"] or fact["subject"] == "unknown" or fact["temporality"] == "unknown":
            add("fact_review_required", "Review content, subject and chronology against its evidence.", fid)
        quote = fact["evidence"]["quote"] if fact["evidence"] else ""
        critical = fact["category"] in ("medication", "allergy", "measurement") or CRITICAL.search(quote + " " + fact["text"])
        if critical and not fact["critical_reviewed"]:
            add("critical_field_review", "Explicitly check medication, allergy and numeric details.", fid, "critical")
        if fact.get("excluded"):
            if len(fact["clarification"].strip()) < 20:
                add("exclusion_requires_reason", "Document why this source content is excluded.", fid, "critical")
            continue
        if AMBIGUITY.search(fact["text"]):
            add("ambiguous_statement", "Clarify the ambiguous statement through a documented clinical correction.", fid, "critical")
        elif AMBIGUITY.search(quote) and (len(fact["clarification"].strip()) < 20 or fact["text"] == quote):
            add("ambiguous_source", "Record the clarified content and clinical basis; the original source remains ambiguous.", fid, "critical")
        elif fact["origin"] == "source_linked" and fact["text"] != quote and len(fact["clarification"].strip()) < 10:
            add("edited_claim_requires_reason", "Document the clinical basis for changing the quoted wording.", fid)
    for segment in transcript["segments"]:
        relevant = [fact for fact in note["facts"] if fact["evidence"] and fact["evidence"]["segment_id"] == segment["segment_id"]]
        if segment["text"].strip() and not relevant:
            add("source_omission", "Include or explicitly exclude every source segment after review.")
        for match in CRITICAL.finditer(segment["text"]):
            if not any(fact["evidence"]["start_char"] <= match.start() and fact["evidence"]["end_char"] >= match.end() for fact in relevant):
                add("critical_source_omission", "A medication, allergy or number in the source is not accounted for.", severity="critical")
                break
    return findings


def render_sections(facts):
    return [{"key": key, "statements": [{"statement_id": fact["fact_id"], "text": fact["text"],
        "fact_ids": [fact["fact_id"]], "origin": fact["origin"]} for fact in facts if fact["section"] == key and not fact.get("excluded")]}
        for key in ("subjective", "objective", "assessment", "plan")]


def render_export(note, approval, format):
    import json
    payload = {"schema_version": "1.0", "status": "approved", "approval": approval, "note": note}
    if format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = ["# Approved clinical note" if format == "markdown" else "APPROVED CLINICAL NOTE",
             f"Encounter: {note['encounter_id']}", f"Version: {note['version']} ({note['id']})",
             f"Approved: {approval['approved_at']}", f"SHA-256: {approval['note_sha256']}", ""]
    for section in note["sections"]:
        lines.append(("## " if format == "markdown" else "") + section["key"].title())
        for statement in section["statements"]:
            lines.append(statement["text"])
            if statement["origin"] == "clinician_entered":
                lines.append("[Clinician-entered addition; not audio-derived.]")
        if not section["statements"]:
            lines.append("Not documented.")
        lines.append("")
    return "\n".join(lines)
