"""Source-spanned clinical entity candidates; deterministic, uncalibrated rules."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.review.clinical import MEDICATION, QUANTITY
from services.review.models import ClinicalAssertion

ClinicalEntityKind = Literal[
    "drug_name",
    "strength",
    "route",
    "frequency",
    "allergy",
    "negation",
    "anatomy",
    "measurement",
    "temporal_relation",
]


_ROUTE = re.compile(
    r"\b(?:by mouth|orally|oral|PO|intravenous|IV|intramuscular|IM|"
    r"subcutaneous|SQ|topical|inhaled|intranasal|rectal|sublingual)\b",
    re.I,
)
_FREQUENCY = re.compile(
    r"\b(?:once|twice|three times|four times) "
    r"(?:(?:a |per )?day|daily)\b|"
    r"\b(?:daily|nightly|weekly|monthly|q\.?d\.?|b\.?i\.?d\.?|"
    r"t\.?i\.?d\.?|q\.?i\.?d\.?|every \d+ hours?)\b",
    re.I,
)
_ALLERGY = re.compile(
    r"\b(?:allerg(?:y|ies)(?:\s+to)?|allergic\s+to)\s+"
    r"(?P<item>penicillin|aspirin|sulfa(?:mides?)?|latex|peanuts?|"
    r"shellfish|eggs?|pollen|adhesives?)\b|"
    r"\b(?P<reverse>penicillin|aspirin|sulfa(?:mides?)?|latex|peanuts?|"
    r"shellfish|eggs?|pollen|adhesives?)\s+allerg(?:y|ies)\b",
    re.I,
)
_NEGATION = re.compile(
    r"\b(?:no|not|never|without|denies|denied|negative for|rules out)\b", re.I
)
_ANATOMY = re.compile(
    r"\b(?:chest|abdomen|abdominal|heart|lung|lungs|throat|neck|back|"
    r"head|brain|left arm|right arm|left leg|right leg|knee|hip|skin|"
    r"stomach|kidney|kidneys|liver|ankle|wrist)\b",
    re.I,
)
_MEASUREMENT = re.compile(
    r"(?<!\w)\d+(?:\.\d+)?\s*(?:mmHg|cm|mm|mL|ml|L|kg|g|lb|lbs|"
    r"°\s?[CF]|degrees?\s+[CF]|bpm|%|percent)\b",
    re.I,
)
_TEMPORAL = re.compile(
    r"\b(?:since|for|before|after|during|until|yesterday|today|tomorrow|"
    r"last night|this morning|onset|currently|previously|recently|"
    r"\d+\s+(?:minutes?|hours?|days?|weeks?|months?|years?)\s+ago)\b",
    re.I,
)


class ClinicalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ClinicalEntityKind
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    assertion: ClinicalAssertion | None = None
    related_to: str | None = None

    @model_validator(mode="after")
    def valid_span(self):
        if self.end_char <= self.start_char:
            raise ValueError("invalid_entity_span")
        if self.kind == "drug_name" and not self.related_to:
            raise ValueError("drug_entity_requires_binding_id")
        return self


def extract_medication_entities(text: str) -> list[ClinicalEntity]:
    """Extract medication and adjacent quantity candidates without rewriting text."""
    if not isinstance(text, str) or not text:
        raise ValueError("clinical_entity_text_required")
    drugs = list(MEDICATION.finditer(text))
    entities = []
    clause_break = re.compile(r";|(?<!\d)[.!?](?!\d)|\b(?:but|however)\b", re.I)
    for index, drug in enumerate(drugs):
        preceding = max(
            (match.end() for match in clause_break.finditer(text, 0, drug.start())),
            default=0,
        )
        following = min(
            (match.start() for match in clause_break.finditer(text, drug.end())),
            default=len(text),
        )
        clause = text[preceding:following]
        negated = bool(
            re.search(r"\b(?:no|not|denies|denied|never|without)\b", clause, re.I)
        )
        uncertain = bool(
            re.search(r"\b(?:maybe|possibly|perhaps|might)\b", clause, re.I)
        )
        assertion: ClinicalAssertion = (
            "uncertain" if uncertain else "negated" if negated else "affirmed"
        )
        binding_id = f"medication-{index}"
        entities.append(
            ClinicalEntity(
                kind="drug_name",
                text=drug.group(),
                start_char=drug.start(),
                end_char=drug.end(),
                assertion=assertion,
                related_to=binding_id,
            )
        )
        next_drug = drugs[index + 1].start() if index + 1 < len(drugs) else len(text)
        span_end = min(next_drug, following)
        for quantity in QUANTITY.finditer(text, drug.end(), span_end):
            entities.append(
                ClinicalEntity(
                    kind="strength",
                    text=quantity.group(),
                    start_char=quantity.start(),
                    end_char=quantity.end(),
                    assertion=assertion,
                    related_to=binding_id,
                )
            )
    return entities


def extract_clinical_entities(text: str) -> list[ClinicalEntity]:
    """Return conservative, source-spanned candidates across the declared types.

    These phrase rules are development aids, not a clinical parser. They do not
    normalize text, infer unstated facts, or authorize any downstream action.
    """
    medication_entities = extract_medication_entities(text)
    entities = list(medication_entities)
    drugs = [entity for entity in medication_entities if entity.kind == "drug_name"]
    clause_break = re.compile(r";|(?<!\d)[.!?](?!\d)|\b(?:but|however)\b", re.I)

    def assertion_at(start: int) -> ClinicalAssertion:
        preceding = max(
            (match.end() for match in clause_break.finditer(text, 0, start)),
            default=0,
        )
        clause = text[preceding:start]
        if re.search(r"\b(?:maybe|possibly|perhaps|might)\b", clause, re.I):
            return "uncertain"
        if _NEGATION.search(clause):
            return "negated"
        return "affirmed"

    def related_medication(start: int) -> str | None:
        prior = [drug for drug in drugs if drug.end_char <= start]
        if not prior:
            return None
        candidate = prior[-1]
        boundary = max(
            (
                match.end()
                for match in clause_break.finditer(text, candidate.end_char, start)
            ),
            default=candidate.end_char,
        )
        return candidate.related_to if start - boundary <= 96 else None

    patterns: tuple[tuple[ClinicalEntityKind, re.Pattern[str]], ...] = (
        ("route", _ROUTE),
        ("frequency", _FREQUENCY),
        ("anatomy", _ANATOMY),
        ("measurement", _MEASUREMENT),
        ("temporal_relation", _TEMPORAL),
        ("negation", _NEGATION),
    )
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            entities.append(
                ClinicalEntity(
                    kind=kind,
                    text=match.group(),
                    start_char=match.start(),
                    end_char=match.end(),
                    assertion=(
                        "negated" if kind == "negation" else assertion_at(match.start())
                    ),
                    related_to=(
                        related_medication(match.start())
                        if kind in {"route", "frequency"}
                        else None
                    ),
                )
            )

    for match in _ALLERGY.finditer(text):
        group = "item" if match.group("item") is not None else "reverse"
        start, end = match.span(group)
        entities.append(
            ClinicalEntity(
                kind="allergy",
                text=text[start:end],
                start_char=start,
                end_char=end,
                assertion=assertion_at(match.start()),
            )
        )
    return sorted(
        entities, key=lambda entity: (entity.start_char, entity.end_char, entity.kind)
    )


def compare_candidate_safety(original: str, alternative: str) -> dict:
    """Flag source-candidate conflicts; agreement is not a truth or adoption gate."""
    if not isinstance(original, str) or not isinstance(alternative, str):
        raise ValueError("candidate_text_required")
    from services.review.clinical import check_claim

    findings = check_claim(original, alternative)
    codes = sorted({finding["code"] for finding in findings})
    risk_codes = {
        "negation_disagreement",
        "negation_scope_disagreement",
        "dose_or_unit_disagreement",
        "medication_or_allergen_disagreement",
        "medication_dose_assignment_disagreement",
    }
    conflicts = [code for code in codes if code in risk_codes]
    return {
        "original_candidate": original,
        "alternative_candidate": alternative,
        "risk_reasons": conflicts,
        "review_required": bool(conflicts),
        "automatic_adoption": False,
        "clinical_truth_verified": False,
        "status": "review_required" if conflicts else "no_rule_conflict_detected",
    }
