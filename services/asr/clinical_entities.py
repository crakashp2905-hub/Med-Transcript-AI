"""Source-spanned clinical entity candidates; deterministic, uncalibrated rules."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.review.clinical import MEDICATION, QUANTITY


class ClinicalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[
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
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    assertion: Literal["affirmed", "negated", "uncertain"] | None = None
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
        assertion = "uncertain" if uncertain else "negated" if negated else "affirmed"
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
