"""Conservative source-span extraction and a separate contradiction checker.

Rules are development heuristics, not calibrated clinical models.
"""
import re
from uuid import uuid4

NEGATION = re.compile(r"\b(no|not|denies|denied|without|never)\b", re.I)
QUANTITY = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units)\b", re.I)
MEDICATION = re.compile(r"\b(?:metformin|warfarin|insulin|amoxicillin|penicillin)\b", re.I)


def extract(transcript):
    result = []
    for segment in transcript["segments"]:
        text = segment["text"]
        # Sentence boundaries preserve decimals. Never resolve pronouns by guessing.
        for match in re.finditer(r"\S(?:.*?)(?:(?<!\d)[.!?](?=\s|$)|$)", text):
            quote = match.group().strip()
            if not quote:
                continue
            start = match.start() + len(match.group())-len(match.group().lstrip())
            category = "other"
            for name, pattern in [("allergy", r"allerg|anaphyl|reaction"),
                    ("medication", r"\b(?:taking|takes|stopped|restart|metformin|insulin|warfarin)\b|\b(?:mg|mcg|ml)\b"),
                    ("plan", r"\b(?:plan|order|refer|follow.up|test)\b"),
                    ("symptom", r"\b(?:pain|cough|fever|headache|nausea|breathless)\b")]:
                if re.search(pattern, quote, re.I):
                    category = name
                    break
            uncertain = bool(re.search(r"\b(?:maybe|possibly|unsure|she|he|it)\b", quote, re.I))
            result.append({"fact_id": str(uuid4()), "category": category,
                "section": "plan" if category == "plan" else "subjective", "text": quote,
                "subject": "family" if re.search(r"\b(?:mother|father|sister|brother)\b", quote, re.I) else "unknown",
                "assertion": "uncertain" if uncertain else "negated" if NEGATION.search(quote) else "affirmed",
                "temporality": "historical" if re.search(r"\b(?:stopped|previously|used to|last month)\b", quote, re.I) else "planned" if re.search(r"\b(?:restart|next week|will)\b", quote, re.I) else "unknown",
                "origin": "source_linked", "reviewed": False, "critical_reviewed": False,
                "extraction_version": "conservative_sentence_spans_v1",
                "clarification": "", "evidence": {"segment_id": segment["segment_id"],
                    "start_char": start, "end_char": start+len(quote), "quote": quote}})
    return result


def check_claim(source, claim):
    from services.evaluation import tokens
    findings = []
    def add(code):
        findings.append({"code": code, "severity": "critical", "blocks_approval": True,
            "source": source, "claim": claim, "validator": "independent_clinical_rules_v1"})
    if bool(NEGATION.search(source)) != bool(NEGATION.search(claim)):
        add("negation_disagreement")
    if QUANTITY.findall(source.lower()) != QUANTITY.findall(claim.lower()):
        add("dose_or_unit_disagreement")
    if MEDICATION.findall(source.lower()) != MEDICATION.findall(claim.lower()):
        add("medication_or_allergen_disagreement")
    for group, code in [(r"\b(?:left|right|bilateral)\b", "laterality_disagreement"),
            (r"\b(?:stopped|restart|previously|current|next week)\b", "temporality_disagreement")]:
        if re.findall(group, source.lower()) != re.findall(group, claim.lower()):
            add(code)
    family = r"\b(?:mother|father|sister|brother|family)\b"
    if re.findall(family, source.lower()) != re.findall(family, claim.lower()):
        add("incorrect_attribution")
    connective = {"patient","reports","report","states","state","i","the","a","an","has","have","is","was","takes","take"}
    novel = set(tokens(claim))-set(tokens(source))-connective
    if novel:
        add("unsupported_claim_terms")
    return findings
