"""Evidence validation and bounded clinician-reviewed template drafting; no diagnostic model."""

import re
import hashlib
from uuid import uuid4

from fastapi import HTTPException
from services.canonical import content_sha256


AMBIGUITY = re.compile(
    r"\b(?:unclear|inaudible|maybe|unsure|not sure)\b|\d+(?:\.\d+)?\s*(?:or|/)\s*\d+",
    re.I,
)
CRITICAL = re.compile(
    r"\b(?:mg|mcg|ml|units|insulin|allerg\w*|metformin|warfarin|dose|dosage)\b|\d", re.I
)
RULES_VERSION = "rules_v5"


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
            if (
                not segment
                or evidence.end_char <= evidence.start_char
                or evidence.end_char > len(segment["text"])
                or segment["text"][evidence.start_char : evidence.end_char]
                != evidence.quote
            ):
                raise HTTPException(422, "invalid_evidence_reference")


def propose_facts(transcript):
    from services.review.clinical import extract

    return extract(transcript)


def findings_for(note, transcript):
    findings = []
    facts_by_id = {f["fact_id"]: f for f in note["facts"]}
    fields_by_code = {
        "dose_or_unit_disagreement": ["dose_value", "dose_unit"],
        "medication_or_allergen_disagreement": ["medication_name", "allergen"],
        "negation_disagreement": ["assertion"],
        "negation_scope_disagreement": ["assertion"],
        "incorrect_attribution": ["subject"],
        "temporality_disagreement": ["temporality"],
        "laterality_disagreement": ["laterality"],
        "ambiguous_source": ["source_uncertainty"],
        "ambiguous_statement": ["statement_text"],
        "critical_field_review_required": ["critical_reviewed"],
        "critical_source_omission": ["source_coverage"],
        "unaccounted_source_content": ["source_coverage"],
        "source_omission": ["source_coverage"],
    }

    def add(
        code,
        message,
        fact_id=None,
        severity="major",
        validator=RULES_VERSION,
        fields=None,
        source_span=None,
    ):
        fact = facts_by_id.get(fact_id)
        evidence = fact.get("evidence") if fact else None
        if source_span is not None:
            segment, start, end = source_span
            evidence = {
                "segment_id": segment["segment_id"],
                "start_char": start,
                "end_char": end,
                "quote": segment["text"][start:end],
            }
        reference = (
            None
            if not evidence
            else {
                "transcript_version_id": transcript.get("id"),
                "segment_id": evidence["segment_id"],
                "start_char": evidence["start_char"],
                "end_char": evidence["end_char"],
                "quote_sha256": hashlib.sha256(
                    evidence["quote"].encode("utf-8")
                ).hexdigest(),
            }
        )
        findings.append(
            {
                "finding_id": str(uuid4()),
                "code": code,
                "message": message,
                "severity": severity,
                "fact_id": fact_id,
                "state": "open",
                "blocks_approval": True,
                "validator_version": validator,
                "mismatch_fields": fields
                or fields_by_code.get(code, ["statement_text"]),
                "source_reference": reference,
            }
        )

    review = transcript.get("review", {})
    if not review.get("english_confirmed"):
        add(
            "language_support_unverified",
            "Confirm supported English against the original source.",
        )
    if (
        not review.get("source_completeness_reviewed")
        or len(review.get("source_review_reason", "").strip()) < 10
    ):
        add(
            "source_review_required",
            "Review the complete source, including untranscribed intervals.",
        )
    if any(
        row.get("role") == "unknown" and row["text"].strip()
        for row in transcript["segments"]
    ):
        add(
            "speaker_roles_unconfirmed",
            "Confirm source speaker roles before attribution.",
        )
    for fact in note["facts"]:
        fid = fact["fact_id"]
        if (
            not fact["reviewed"]
            or fact["subject"] == "unknown"
            or fact["temporality"] == "unknown"
        ):
            add(
                "fact_review_required",
                "Review content, subject and chronology against its evidence.",
                fid,
            )
        if fact["assertion"] == "not_stated" and not fact.get("excluded"):
            add(
                "fact_review_required",
                "A documented assertion cannot retain a not-stated polarity label.",
                fid,
            )
        quote = fact["evidence"]["quote"] if fact["evidence"] else ""
        if fact["origin"] == "source_linked" and not fact.get("excluded"):
            from services.review.clinical import check_claim

            for disagreement in check_claim(quote, fact["text"]):
                add(
                    disagreement["code"],
                    "The saved claim is not established by its quoted source. Correct the source or record a separate clinician addition.",
                    fid,
                    "critical",
                    validator=disagreement.get("validator", RULES_VERSION),
                )
            from services.review.clinical import check_fact_slots

            for disagreement in check_fact_slots(quote, fact):
                add(
                    disagreement["code"],
                    f"Structured field {disagreement['field']} is not supported by the selected evidence.",
                    fid,
                    "critical",
                    validator="typed_clinical_fields_v1",
                    fields=[disagreement["field"]],
                )
        critical = fact["category"] in (
            "medication",
            "allergy",
            "measurement",
        ) or CRITICAL.search(quote + " " + fact["text"])
        if critical and not fact["critical_reviewed"]:
            add(
                "critical_field_review",
                "Explicitly check medication, allergy and numeric details.",
                fid,
                "critical",
            )
        if fact.get("excluded"):
            if len(fact["clarification"].strip()) < 20:
                add(
                    "exclusion_requires_reason",
                    "Document why this source content is excluded.",
                    fid,
                    "critical",
                )
            continue
        if AMBIGUITY.search(fact["text"]):
            add(
                "ambiguous_statement",
                "Clarify the ambiguous statement through a documented clinical correction.",
                fid,
                "critical",
            )
        elif AMBIGUITY.search(quote) and (
            len(fact["clarification"].strip()) < 20 or fact["text"] == quote
        ):
            add(
                "ambiguous_source",
                "Record the clarified content and clinical basis; the original source remains ambiguous.",
                fid,
                "critical",
            )
        elif (
            fact["origin"] == "source_linked"
            and fact["text"] != quote
            and len(fact["clarification"].strip()) < 10
        ):
            add(
                "edited_claim_requires_reason",
                "Document the clinical basis for changing the quoted wording.",
                fid,
            )
    for segment in transcript["segments"]:
        relevant = [
            fact
            for fact in note["facts"]
            if fact["evidence"]
            and fact["evidence"]["segment_id"] == segment["segment_id"]
        ]
        if segment["text"].strip() and not relevant:
            add(
                "source_omission",
                "This source segment has no reviewed fact or explicit exclusion.",
                source_span=(segment, 0, len(segment["text"])),
            )
        for match in CRITICAL.finditer(segment["text"]):
            if not any(
                fact["evidence"]["start_char"] <= match.start()
                and fact["evidence"]["end_char"] >= match.end()
                for fact in relevant
            ):
                add(
                    "critical_source_omission",
                    "This medication, allergy or number in the source has no reviewed fact or explicit exclusion.",
                    severity="critical",
                    source_span=(segment, match.start(), match.end()),
                )
                break
        ignored = {
            "and",
            "but",
            "the",
            "a",
            "an",
            "patient",
            "reports",
            "report",
            "states",
            "state",
            "i",
            "has",
            "have",
            "is",
            "was",
            "takes",
            "take",
            "taking",
        }
        for match in re.finditer(r"\b[\w]+(?:[.'-][\w]+)*\b", segment["text"]):
            if match.group().lower() in ignored:
                continue
            if not any(
                f["evidence"]["start_char"] <= match.start()
                and f["evidence"]["end_char"] >= match.end()
                for f in relevant
            ):
                add(
                    "unaccounted_source_content",
                    "This source word falls outside all included or explicitly excluded evidence spans.",
                    severity="critical",
                    source_span=(segment, match.start(), match.end()),
                )
                break
    return findings


def directional_coverage(note, transcript, findings=None):
    """Summarize source-to-note omissions and note-to-source grounding failures."""
    findings = findings if findings is not None else findings_for(note, transcript)
    source_codes = {
        "source_omission",
        "critical_source_omission",
        "unaccounted_source_content",
        "dose_or_unit_disagreement",
        "medication_or_allergen_disagreement",
        "medication_dose_assignment_disagreement",
        "negation_disagreement",
        "negation_scope_disagreement",
        "incorrect_attribution",
        "temporality_disagreement",
        "laterality_disagreement",
        "structured_field_disagreement",
        "unsupported_claim_terms",
        "omitted_source_terms",
    }
    note_codes = source_codes - {
        "source_omission",
        "critical_source_omission",
        "unaccounted_source_content",
    }

    def rows_for(codes):
        rows = [row for row in findings if row["code"] in codes]
        return [
            {
                "finding_id": row["finding_id"],
                "code": row["code"],
                "materiality": row["severity"],
                "fact_id": row.get("fact_id"),
                "source_reference": {
                    key: value
                    for key, value in (row.get("source_reference") or {}).items()
                    if key
                    in {
                        "transcript_version_id",
                        "segment_id",
                        "start_char",
                        "end_char",
                        "quote_sha256",
                    }
                },
            }
            for row in rows
        ]

    source_rows = rows_for(source_codes)
    note_rows = rows_for(note_codes)
    detection_receipts = []
    for finding in findings:
        reference = finding.get("source_reference") or {}
        receipt = {
            "schema_version": "redacted_detection_receipt_v1",
            "finding_id": finding["finding_id"],
            "finding_code": finding["code"],
            "severity": finding["severity"],
            "validator_version": finding["validator_version"],
            "fact_id": finding.get("fact_id"),
            "note_version_id": note.get("id"),
            "transcript_version_id": transcript.get("id"),
            "source_reference": {
                key: reference[key]
                for key in (
                    "transcript_version_id",
                    "segment_id",
                    "start_char",
                    "end_char",
                    "quote_sha256",
                )
                if key in reference
            },
            "raw_source_text_included": False,
            "raw_note_text_included": False,
            "model_prompt_or_completion_included": False,
            "egress_scope": "local_tenant_scoped_audit_only",
        }
        receipt["receipt_sha256"] = content_sha256(receipt)
        detection_receipts.append(receipt)
    manual_count = sum(
        fact.get("origin") in {"clinician_entered", "manual_no_audio_evidence"}
        for fact in note.get("facts", [])
    )
    return {
        "schema_version": "directional_source_note_coverage_v1",
        "source_not_in_note": {
            "status": "review_required" if source_rows else "no_rule_detected",
            "finding_count": len(source_rows),
            "by_materiality": {
                grade: sum(row["materiality"] == grade for row in source_rows)
                for grade in ("critical", "major", "minor")
            },
            "findings": source_rows,
        },
        "note_not_in_source": {
            "status": "review_required" if note_rows else "no_rule_detected",
            "finding_count": len(note_rows),
            "by_materiality": {
                grade: sum(row["materiality"] == grade for row in note_rows)
                for grade in ("critical", "major", "minor")
            },
            "findings": note_rows,
        },
        "unverifiable_manual_fact_count": manual_count,
        "redacted_detection_receipts": detection_receipts,
        "materiality_method": "deterministic_review_rule_severity_not_independent_clinical_gold",
        "raw_source_text_included": False,
        "clinical_adjudication": "not_performed",
        "approval_authority": False,
    }


def current_safety_recheck(note, transcript, report):
    """Additional current-rule findings never rewrite or clear historical reports."""
    if report.get("validator_version") == RULES_VERSION:
        return None
    findings = findings_for(note, transcript)
    return {
        "validator_version": RULES_VERSION,
        "saved_validator_version": report.get("validator_version"),
        "scope": "current_rules_against_exact_saved_source",
        "gate": "blocked" if findings else "ready",
        "findings": findings,
        "historical_approval_modified": False,
        "cannot_clear_saved_findings": True,
    }


def render_sections(facts, transcript_version_id=None):
    return [
        {
            "key": key,
            "statements": [
                {
                    "statement_id": fact["fact_id"],
                    "text": fact["text"],
                    "fact_ids": [fact["fact_id"]],
                    "origin": fact["origin"],
                    "source_version_id": transcript_version_id
                    if fact["origin"] == "source_linked"
                    else None,
                    "evidence": fact.get("evidence")
                    if fact.get("origin") == "source_linked"
                    else None,
                    "owner_clinician_id": fact.get("owner_clinician_id"),
                }
                for fact in facts
                if fact["section"] == key and not fact.get("excluded")
            ],
        }
        for key in ("subjective", "objective", "assessment", "plan")
    ]


def render_export(note, approval, format, source=None):
    import json
    from services.clinical_limitations import CLINICAL_LIMITATIONS

    if format == "fhir":
        from services.review.presentation import fhir_document

        return fhir_document(note, approval, source)
    payload = {
        "schema_version": "1.0",
        "status": "approved",
        "approval": approval,
        "note": note,
        "limitations": list(CLINICAL_LIMITATIONS),
    }
    if source is not None:
        payload["source"] = source
    if format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = [
        "# Approved clinical note"
        if format == "markdown"
        else "APPROVED CLINICAL NOTE",
        f"Encounter: {note['encounter_id']}",
        f"Version: {note['version']} ({note['id']})",
        f"Approved: {approval['approved_at']}",
        f"SHA-256: {approval['note_sha256']}",
        "",
    ]
    if source is not None:
        attribution = source.get("provenance", {}).get(
            "attribution", "No source-license attribution recorded."
        )
        lines.extend(
            [
                "Source transcript: " + source["transcript_version_id"],
                escape_markdown(attribution) if format == "markdown" else attribution,
                "Independent clinical gold: false; recipient EHR conformance: untested.",
                *CLINICAL_LIMITATIONS,
                "",
            ]
        )
    for section in note["sections"]:
        lines.append(("## " if format == "markdown" else "") + section["key"].title())
        for statement in section["statements"]:
            lines.append(
                escape_markdown(statement["text"])
                if format == "markdown"
                else statement["text"]
            )
            if statement["origin"] in {
                "clinician_entered",
                "manual_no_audio_evidence",
            }:
                if statement.get("evidence") is not None:
                    raise ValueError("clinician_statement_cannot_claim_source_evidence")
                owner = statement.get("owner_clinician_id")
                lines.append(
                    "[Clinician-entered addition; not audio-derived.]"
                    if owner is None
                    else "[Clinician-entered addition; source: no audio evidence; owner clinician: "
                    + str(owner)
                    + ".]"
                )
            elif statement["origin"] == "source_linked":
                evidence = statement.get("evidence")
                source_version_id = statement.get("source_version_id")
                if (
                    not source_version_id
                    or not isinstance(evidence, dict)
                    or not isinstance(evidence.get("quote"), str)
                    or not evidence.get("quote")
                    or not isinstance(evidence.get("segment_id"), str)
                    or type(evidence.get("start_char")) is not int
                    or type(evidence.get("end_char")) is not int
                    or evidence["start_char"] < 0
                    or evidence["end_char"] <= evidence["start_char"]
                    or evidence["end_char"] - evidence["start_char"]
                    != len(evidence["quote"])
                ):
                    raise ValueError("approved_statement_source_missing")
                quote_sha256 = hashlib.sha256(
                    evidence["quote"].encode("utf-8")
                ).hexdigest()
                lines.append(
                    "[Source: transcript "
                    f"{source_version_id}; segment {evidence['segment_id']}; "
                    f"characters {evidence['start_char']}-{evidence['end_char']}; "
                    f"quote SHA-256 {quote_sha256}.]"
                )
            else:
                raise ValueError("approved_statement_origin_missing")
        if not section["statements"]:
            lines.append("Not documented.")
        lines.append("")
    return "\n".join(lines)


def escape_markdown(text):
    import html

    return re.sub(r"([\\`*_{}\[\]()#+.!|])", r"\\\1", html.escape(text, quote=False))
