"""Conservative source-span extraction and a separate contradiction checker.

Rules are development heuristics, not calibrated clinical models.
"""

import re
from collections import Counter
from decimal import Decimal
from uuid import uuid4

NEGATION = re.compile(r"\b(no|not|denies|denied|without|never)\b", re.I)
QUANTITY = re.compile(
    r"(?<![\w.])(?P<value>\d+(?:\.\d+)?|\.\d+)\s*(?P<unit>mcg|mg|kg|g|ml|l|units)\b",
    re.I,
)
MEDICATION = re.compile(
    r"\b(?:metformin|warfarin|insulin|amoxicillin|penicillin|ibuprofen|paracetamol|lisinopril|atorvastatin"
    r"|aspirin|amlodipine|losartan|apixaban|rivaroxaban|levothyroxine|omeprazole|salbutamol|albuterol|prednisolone|prednisone|furosemide)\b",
    re.I,
)
SYMPTOMS = re.compile(
    r"\b(?:pain|cough|fever|headache|nausea|breathlessness|rash|vomiting|diarrhea"
    r"|wheeze|wheezing|dizziness|syncope|swelling)\b",
    re.I,
)
ALLERGY_REACTIONS = re.compile(
    r"\b(?:anaphylaxis|anaphylactic reaction|hives|rash|swelling|itching|wheezing|shortness of breath|nausea|vomiting)\b",
    re.I,
)
MEDICATION_ACTIONS = (
    (
        "recommend",
        re.compile(r"\b(?:recommend(?:ed|s|ing)?|suggest(?:ed|s|ing)?)\b", re.I),
    ),
    ("order", re.compile(r"\b(?:order(?:ed|s|ing)?|prescrib(?:e|ed|es|ing))\b", re.I)),
    (
        "discuss",
        re.compile(r"\b(?:discuss(?:ed|es|ing)?|consider(?:ed|s|ing)?)\b", re.I),
    ),
    (
        "stop",
        re.compile(r"\b(?:stop(?:ped|s|ping)?|discontinue(?:d|s)?|ceased?)\b", re.I),
    ),
    ("hold", re.compile(r"\b(?:hold(?:s|ing)?|held|on hold)\b", re.I)),
    ("continue", re.compile(r"\b(?:continue(?:d|s|ing)?|keep taking)\b", re.I)),
    (
        "start",
        re.compile(
            r"\b(?:start(?:ed|s|ing)?|begin(?:s|ning)?|began|restart(?:ed|s|ing)?)\b",
            re.I,
        ),
    ),
)


def quantity_signature(text):
    scales = {
        "mcg": ("mass", Decimal(".001")),
        "mg": ("mass", Decimal(1)),
        "g": ("mass", Decimal(1000)),
        "kg": ("mass", Decimal(1000000)),
        "ml": ("volume", Decimal(1)),
        "l": ("volume", Decimal(1000)),
        "units": ("units", Decimal(1)),
    }
    return Counter(
        (
            scales[m["unit"].lower()][0],
            Decimal(m["value"]) * scales[m["unit"].lower()][1],
        )
        for m in QUANTITY.finditer(text)
    )


def medication_associations(text):
    """Associate local dose/frequency spans only when each drug has one clear span."""
    drugs = list(MEDICATION.finditer(text))
    result = []
    for index, drug in enumerate(drugs):
        end = drugs[index + 1].start() if index + 1 < len(drugs) else len(text)
        window = text[drug.end() : end]
        doses = list(QUANTITY.finditer(window))
        frequencies = list(
            re.finditer(
                r"\b(?:once daily|twice daily|three times daily|daily|weekly)\b",
                window,
                re.I,
            )
        )
        if len(doses) > 1 or len(frequencies) > 1:
            result.append(
                {
                    "medication_name": drug.group(),
                    "dose": None,
                    "frequency": None,
                    "ambiguous": True,
                }
            )
        else:
            result.append(
                {
                    "medication_name": drug.group(),
                    "dose": doses[0].group() if doses else None,
                    "frequency": frequencies[0].group() if frequencies else None,
                    "ambiguous": False,
                }
            )
    return result


def atomic_spans(text):
    # Only split explicit new assertions. Never distribute an implicit negation.
    boundary = re.compile(
        r"[;.!?](?=\s|$)(?!\d)|\b(?:and|but)\s+(?=(?:denies|denied|no|not|reports|has|takes|taking|stopped|stop|discontinue|hold|held|continue|start|begin|restart|recommend|order|prescribe|mother|father|metformin|warfarin|insulin|amoxicillin|penicillin)\b)|\bbut\s+(?="
        + SYMPTOMS.pattern
        + r")",
        re.I,
    )
    start = 0
    for match in boundary.finditer(text):
        end = match.end() if text[match.start()] in ";.!?" else match.start()
        raw = text[start:end]
        if raw.strip():
            a = start + len(raw) - len(raw.lstrip())
            b = end - len(raw) + len(raw.rstrip())
            yield a, b, text[a:b]
        start = match.end()
    raw = text[start:]
    if raw.strip():
        a = start + len(raw) - len(raw.lstrip())
        b = len(text) - len(raw) + len(raw.rstrip())
        yield a, b, text[a:b]


def medication_temporality(text):
    if re.search(
        r"\b(?:previously|used to|last month|in the past|stopped|discontinued|no longer)\b",
        text,
        re.I,
    ):
        return "historical"
    if re.search(
        r"\b(?:will|next week|tomorrow|plan to|plans to|going to|should start|recommend(?:ed)? (?:to )?start|restart)\b",
        text,
        re.I,
    ):
        return "planned"
    if re.search(
        r"\b(?:currently|now|still taking|taking|takes|continue(?:s|d|ing)?|on)\b",
        text,
        re.I,
    ):
        return "current"
    return "unknown"


def extract(transcript):
    result = []
    for segment in transcript["segments"]:
        text = segment["text"]
        # Sentence boundaries preserve decimals. Never resolve pronouns by guessing.
        for start, end, quote in atomic_spans(text):
            if not quote:
                continue
            category = "other"
            for name, pattern in [
                (
                    "allergy",
                    r"allerg|anaphyl|reaction|hives|rash|swelling|itching|wheezing|shortness of breath",
                ),
                (
                    "medication",
                    MEDICATION.pattern
                    + r"|\b(?:taking|takes|stopped|restart|mg|mcg|ml)\b",
                ),
                ("plan", r"\b(?:plan|order|refer|follow.up|test)\b"),
                ("symptom", r"\b(?:pain|cough|fever|headache|nausea|breathless)\b"),
            ]:
                if re.search(pattern, quote, re.I):
                    category = name
                    break
            possible = bool(
                re.search(r"\b(?:maybe|possibly|might|could|perhaps)\b", quote, re.I)
            )
            questioned = "?" in quote or bool(
                re.search(r"\b(?:whether|question(?:s|ed)?|asked if)\b", quote, re.I)
            )
            ambiguous = bool(
                re.search(r"\b(?:unsure|she|he|it)\b", quote, re.I)
            ) or bool(NEGATION.search(quote) and re.search(r"\band\b", quote, re.I))
            uncertain = possible or questioned or ambiguous
            uncertainty = (
                "possible"
                if possible
                else "questioned"
                if questioned
                else "ambiguous"
                if ambiguous
                else "certain"
            )
            action = next(
                (
                    action
                    for action, pattern in MEDICATION_ACTIONS
                    if pattern.search(quote)
                ),
                "unknown",
            )
            fact = {
                "fact_id": str(uuid4()),
                "category": category,
                "section": "plan" if category == "plan" else "subjective",
                "text": quote,
                "subject": "family"
                if re.search(r"\b(?:mother|father|sister|brother)\b", quote, re.I)
                else "unknown",
                "assertion": "uncertain"
                if uncertain
                else "negated"
                if NEGATION.search(quote)
                else "affirmed",
                "uncertainty": uncertainty,
                "action": action if category == "medication" else "unknown",
                "temporality": medication_temporality(quote)
                if category == "medication"
                else "historical"
                if re.search(r"\b(?:previously|used to|last month)\b", quote, re.I)
                else "planned"
                if re.search(r"\b(?:next week|will)\b", quote, re.I)
                else "unknown",
                "origin": "source_linked",
                "source_modality": "transcript",
                "reviewed": False,
                "critical_reviewed": False,
                "extraction_version": "conservative_atomic_spans_v2",
                "clarification": "",
                "evidence": {
                    "segment_id": segment["segment_id"],
                    "start_char": start,
                    "end_char": end,
                    "quote": quote,
                },
            }
            medications = list(MEDICATION.finditer(quote))
            quantities = list(QUANTITY.finditer(quote))
            if category == "medication" and len(medications) == 1:
                fact["medication_name"] = medications[0].group()
                fact["concept"] = medications[0].group().lower()
                if len(quantities) == 1:
                    fact.update(
                        dose_value=quantities[0]["value"],
                        dose_unit=quantities[0]["unit"],
                    )
            if category == "medication":
                routes = list(
                    re.finditer(
                        r"\b(?:orally|by mouth|intravenously|subcutaneously|topically)\b",
                        quote,
                        re.I,
                    )
                )
                frequencies = list(
                    re.finditer(
                        r"\b(?:once daily|twice daily|three times daily|daily|weekly)\b",
                        quote,
                        re.I,
                    )
                )
                durations = list(
                    re.finditer(
                        r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:days?|weeks?|months?)\b",
                        quote,
                        re.I,
                    )
                )
                if len(routes) == 1:
                    fact["route"] = routes[0].group()
                if len(frequencies) == 1:
                    fact["frequency"] = frequencies[0].group()
                if len(durations) == 1:
                    fact["duration"] = durations[0].group()
            if category == "allergy":
                fact["allergy_severity"] = "unknown"
                allergens = list(
                    re.finditer(
                        r"\b(?:allergic|allergy|sensitivity|reaction)\s+(?:to|with)\s+([A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,2}?)(?=\s+(?:with|causes?|caused|resulting|and)\b|[,.!?;]|$)",
                        quote,
                        re.I,
                    )
                )
                if len(medications) == 1:
                    fact["allergen"] = medications[0].group()
                elif len(allergens) == 1:
                    candidate = allergens[0].group(1)
                    if candidate.casefold() not in {"it", "that", "them", "this"}:
                        fact["allergen"] = candidate
                reactions = list(ALLERGY_REACTIONS.finditer(quote))
                if reactions:
                    fact["allergy_reaction"] = ", ".join(
                        dict.fromkeys(match.group() for match in reactions)
                    )
                severities = list(
                    re.finditer(r"\b(?:mild|moderate|severe)\b", quote, re.I)
                )
                if len(severities) == 1:
                    fact["allergy_severity"] = severities[0].group().lower()
            side = re.findall(r"\b(?:left|right|bilateral)\b", quote, re.I)
            if len(side) == 1:
                fact["laterality"] = side[0].lower()
            result.append(fact)
    return result


def check_claim(source, claim, *, include_relationships=True):
    from services.evaluation import tokens

    findings = []

    def add(code):
        findings.append(
            {
                "code": code,
                "severity": "critical",
                "blocks_approval": True,
                "source": source,
                "claim": claim,
                "validator": "independent_clinical_rules_v2",
            }
        )

    if bool(NEGATION.search(source)) != bool(NEGATION.search(claim)):
        add("negation_disagreement")
    if quantity_signature(source) != quantity_signature(claim):
        add("dose_or_unit_disagreement")
    if MEDICATION.findall(source.lower()) != MEDICATION.findall(claim.lower()):
        add("medication_or_allergen_disagreement")
    for group, code in [
        (r"\b(?:left|right|bilateral)\b", "laterality_disagreement"),
        (
            r"\b(?:stopped|restart|previously|current|next week)\b",
            "temporality_disagreement",
        ),
    ]:
        if re.findall(group, source.lower()) != re.findall(group, claim.lower()):
            add(code)
    family = r"\b(?:mother|father|sister|brother|family)\b"
    if re.findall(family, source.lower()) != re.findall(family, claim.lower()):
        add("incorrect_attribution")

    def drug_doses(text):
        drugs = list(MEDICATION.finditer(text))
        return [
            (
                m.group().lower(),
                quantity_signature(
                    text[
                        m.end() : drugs[i + 1].start()
                        if i + 1 < len(drugs)
                        else len(text)
                    ]
                ),
            )
            for i, m in enumerate(drugs)
        ]

    if MEDICATION.findall(source.lower()) == MEDICATION.findall(
        claim.lower()
    ) and drug_doses(source) != drug_doses(claim):
        add("medication_dose_assignment_disagreement")

    def polarity(text):
        return {
            m.group().lower(): bool(NEGATION.search(part))
            for part in re.split(r"\b(?:and|but)\b|[;.!?]", text, flags=re.I)
            for m in SYMPTOMS.finditer(part)
        }

    if polarity(source).keys() == polarity(claim).keys() and polarity(
        source
    ) != polarity(claim):
        add("negation_scope_disagreement")
    connective = {
        "patient",
        "reports",
        "report",
        "states",
        "state",
        "i",
        "the",
        "a",
        "an",
        "has",
        "have",
        "is",
        "was",
        "takes",
        "take",
        "and",
        "but",
    }
    original_words = set(tokens(QUANTITY.sub("", source)))
    claimed_words = set(tokens(QUANTITY.sub("", claim)))
    novel = claimed_words - original_words - connective
    if novel:
        add("unsupported_claim_terms")
    if original_words - claimed_words - connective:
        add("omitted_source_terms")
    from services.review.relationships import disagreement

    if include_relationships and disagreement(source, claim):
        add("clinical_relationship_disagreement")
        findings[-1]["validator"] = "explicit_relationships_v1"
    return findings


def check_fact_slots(source, fact):
    """Validate supplied structured slots; empty slots are unknown, never invented."""
    findings = []

    def add(field):
        findings.append(
            {
                "code": "structured_field_disagreement",
                "field": field,
                "severity": "critical",
                "blocks_approval": True,
            }
        )

    for field in (
        "medication_name",
        "allergen",
        "route",
        "frequency",
        "duration",
        "allergy_reaction",
        "anatomical_site",
        "concept",
    ):
        value = fact.get(field)
        if value and not re.search(
            r"(?<!\w)" + re.escape(value) + r"(?!\w)", source, re.I
        ):
            add(field)
    value, unit = fact.get("dose_value"), fact.get("dose_unit")
    if value or unit:
        try:
            supplied = quantity_signature(f"{value or ''} {unit or ''}")
            if not supplied or not supplied <= quantity_signature(source):
                add("dose_value_or_unit")
        except Exception:
            add("dose_value_or_unit")
    # Joint binding matters: a dose/reaction elsewhere in the quote is not evidence for this drug.
    anchor = fact.get("medication_name") or fact.get("allergen")
    if anchor:
        clauses = [
            part
            for part in re.split(r"(?<=[;.!?])\s+|\b(?:and|but)\b", source, flags=re.I)
            if re.search(r"(?<!\w)" + re.escape(anchor) + r"(?!\w)", part, re.I)
        ]
        if clauses:
            if any(
                len(set(m.group().lower() for m in MEDICATION.finditer(part))) > 1
                for part in clauses
            ):
                add("ambiguous_medication_relationship")
            else:
                for field in ("route", "frequency", "duration", "allergy_reaction"):
                    supplied = fact.get(field)
                    if supplied and not any(
                        re.search(
                            r"(?<!\w)" + re.escape(supplied) + r"(?!\w)", part, re.I
                        )
                        for part in clauses
                    ):
                        add(field + "_relationship")
                if value or unit:
                    supplied = quantity_signature(f"{value or ''} {unit or ''}")
                    if supplied and not any(
                        supplied <= quantity_signature(part) for part in clauses
                    ):
                        add("dose_medication_relationship")
    if fact.get("laterality", "unknown") != "unknown" and not re.search(
        r"\b" + re.escape(fact["laterality"]) + r"\b", source, re.I
    ):
        add("laterality")
    if fact.get("subject") == "patient" and re.search(
        r"\b(?:mother|father|sister|brother)\b", source, re.I
    ):
        add("subject")
    if fact.get("assertion") in ("affirmed", "negated"):
        if len(list(atomic_spans(source))) > 1 or (
            fact["assertion"] == "negated"
        ) != bool(NEGATION.search(source)):
            add("assertion")
    historical = bool(
        re.search(r"\b(?:stopped|previously|used to|last month)\b", source, re.I)
    )
    planned = bool(re.search(r"\b(?:restart|next week|will)\b", source, re.I))
    if (
        historical
        and fact.get("temporality") in ("current", "planned")
        or planned
        and not historical
        and fact.get("temporality") in ("current", "historical")
    ):
        add("temporality")
    return findings
