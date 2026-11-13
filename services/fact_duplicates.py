"""Detect duplicate facts without deleting contradictions or temporal variants."""

import hashlib


def detect(facts):
    groups = {}
    for fact in facts:
        key = (
            fact.get("category"),
            fact.get("concept"),
            fact.get("text", "").casefold(),
        )
        groups.setdefault(key, []).append(fact)
    duplicates = [rows for rows in groups.values() if len(rows) > 1]
    duplicate_groups = []
    for rows in duplicates:
        occurrences = []
        for row in rows:
            evidence = row.get("evidence") or {}
            quote = evidence.get("quote")
            reference = {
                key: evidence[key]
                for key in ("segment_id", "start_char", "end_char")
                if key in evidence
            }
            if isinstance(quote, str):
                reference["quote_sha256"] = hashlib.sha256(
                    quote.encode("utf-8")
                ).hexdigest()
            occurrences.append(
                {
                    "fact_id": row.get("fact_id"),
                    "temporality": row.get("temporality", "unknown"),
                    "evidence_reference": reference,
                }
            )
        temporalities = sorted({row["temporality"] for row in occurrences})
        duplicate_groups.append(
            {
                "fact_ids": [row.get("fact_id") for row in rows],
                "occurrences": occurrences,
                "temporal_variants": temporalities,
                "temporal_conflict": len(temporalities) > 1,
                "clinician_review_required": True,
                "automatic_suppression": False,
            }
        )
    return {
        "groups": duplicate_groups,
        "count": sum(len(rows) - 1 for rows in duplicates),
        "preserved_facts": len(facts),
        "contradictions_retained": True,
        "raw_source_text_included": False,
    }
