"""Explicit lexical bindings, not clinical inference or independent gold."""

from collections import Counter
import hashlib
import re
from typing import Literal
from pydantic import Field
from services.review.models import ClinicalAssertion, Strict, Evidence
from services.review.clinical import (
    MEDICATION,
    QUANTITY,
    SYMPTOMS,
    NEGATION,
    quantity_signature,
)

ENTITY = re.compile(
    MEDICATION.pattern
    + "|"
    + SYMPTOMS.pattern
    + r"|\b(?:asthma|diabetes|hypertension|glucose|bleeding)\b",
    re.I,
)
SUBJECT = re.compile(
    r"\b(patient|mother|father|sister|brother|caregiver|maternal|paternal)\b", re.I
)
ACTION = re.compile(r"\b(stop|stopped|continue|hold|restart|reduce|increase)\b", re.I)
TIMING = re.compile(
    r"\b(?:(?:before|after|at)\s+(?:breakfast|lunch|dinner|bedtime)|twice daily|once daily|three times daily|daily|weekly|today|yesterday|this morning|this afternoon|this evening|morning|evening|bedtime|next week|previously|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:days?|weeks?|months?))\b",
    re.I,
)
FREQUENCY = re.compile(
    r"\b(?:once|twice|three times)\s+(?:daily|a day)|\b(?:daily|weekly)\b",
    re.I,
)
MENTIONED_DURATION = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:days?|weeks?|months?)\b",
    re.I,
)
ROUTE = re.compile(
    r"\b(?:orally|oral|by mouth|intravenous|intravenously|subcutaneous|subcutaneously|topical|topically)\b",
    re.I,
)
NUMBERS = dict(
    zip(
        ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"),
        map(str, range(1, 11)),
    )
)


class ClinicalRelationship(Strict):
    subject: Literal[
        "patient", "mother", "father", "sister", "brother", "caregiver", "unknown"
    ]
    entities: list[str] = Field(max_length=30)
    quantities: list[tuple[str, str]] = Field(max_length=30)
    timing: list[str] = Field(max_length=30)
    routes: list[str] = Field(max_length=30)
    actions: list[str] = Field(max_length=30)
    condition: str = Field(max_length=4000)
    assertion: ClinicalAssertion
    evidence: Evidence
    review_required: bool = True
    interpretation: str = "explicit_lexical_binding_not_clinical_validation"


class RelationshipNode(Strict):
    node_id: str
    node_type: Literal[
        "medication",
        "symptom",
        "condition",
        "dose",
        "route",
        "frequency",
        "duration",
        "temporality",
        "subject",
        "assertion",
        "action",
    ]
    value: str


class RelationshipEdge(Strict):
    from_node_id: str
    to_node_id: str
    relation_type: Literal[
        "dose",
        "route",
        "frequency",
        "duration",
        "temporality",
        "subject",
        "negation",
        "assertion",
        "action",
    ]
    evidence: Evidence
    review_required: bool = True


def canonical(text):
    text = text.lower()
    for a, b in NUMBERS.items():
        text = re.sub(r"\b" + a + r"\b", b, text)
    return text


def bindings(text):
    # Never assign a family member or resolve a pronoun by proximity.
    global_drugs = set(m.group().lower() for m in MEDICATION.finditer(text))
    boundary = re.compile(r"(?<=[;.!?])\s+|\b(?:and|but)\b", re.I)
    start = 0
    for end in [m.start() for m in boundary.finditer(text)] + [len(text)]:
        raw = text[start:end]
        quote = raw.strip()
        a = start + len(raw) - len(raw.lstrip())
        b = a + len(quote)
        next_match = boundary.match(text, end)
        start = next_match.end() if next_match else end
        if not quote:
            continue
        normalized = canonical(quote)
        entities = sorted(set(m.group().lower() for m in ENTITY.finditer(quote)))
        if (
            len(global_drugs) == 1
            and not MEDICATION.search(quote)
            and (quantity_signature(quote) or TIMING.search(quote))
        ):
            entities = sorted(set(entities) | global_drugs)
        if not entities:
            continue
        subjects = {m.group().lower() for m in SUBJECT.finditer(quote)}
        subjects = {
            {"maternal": "mother", "paternal": "father"}.get(s, s) for s in subjects
        }
        subject = next(iter(subjects)) if len(subjects) == 1 else "unknown"
        condition = ""
        if re.search(r"\bif\b", normalized):
            if normalized.startswith("if ") and "," in normalized:
                condition = normalized[3:].split(",", 1)[0].strip()
            else:
                condition = re.split(r"\bif\b", normalized, maxsplit=1)[1].strip(" .;")
        row = {
            "subject": subject,
            "entities": entities,
            "quantities": sorted(
                (unit, str(value.normalize()))
                for (unit, value), count in quantity_signature(quote).items()
                for _ in range(count)
            ),
            "timing": sorted(m.group().lower() for m in TIMING.finditer(normalized)),
            "routes": sorted(
                {
                    "orally": "oral",
                    "by mouth": "oral",
                    "intravenously": "intravenous",
                    "subcutaneously": "subcutaneous",
                    "topically": "topical",
                }.get(m.group().lower(), m.group().lower())
                for m in ROUTE.finditer(quote)
            ),
            "actions": sorted(m.group().lower() for m in ACTION.finditer(quote)),
            "condition": condition,
            "assertion": "uncertain"
            if re.search(r"\b(?:maybe|possibly|unsure)\b", quote, re.I)
            else "negated"
            if NEGATION.search(quote)
            else "affirmed",
        }
        yield a, b, quote, row


def signature(text):
    import json

    return Counter(json.dumps(row, sort_keys=True) for _, _, _, row in bindings(text))


def disagreement(source, claim):
    a, b = signature(source), signature(claim)
    source_entities = Counter(
        e for _, _, _, r in bindings(source) for e in r["entities"]
    )
    claim_entities = Counter(e for _, _, _, r in bindings(claim) for e in r["entities"])
    return bool(a and b and source_entities == claim_entities and a != b)


def analyze_transcript(transcript):
    rows = []
    nodes = {}
    edges = []

    def add_node(node_id, node_type, value):
        nodes[node_id] = RelationshipNode(
            node_id=node_id, node_type=node_type, value=value
        )

    for segment in transcript["segments"]:
        for a, b, quote, row in bindings(segment["text"]):
            evidence = Evidence(
                segment_id=segment["segment_id"],
                start_char=a,
                end_char=b,
                quote=quote,
            )
            evidence_model = evidence
            row_id = hashlib.sha256(
                f"{segment['segment_id']}:{a}:{b}:{quote}".encode("utf-8")
            ).hexdigest()
            relation_id = f"source_relation:{row_id}"
            rows.append(
                ClinicalRelationship(**row, evidence=evidence).model_dump(mode="json")
            )
            assertion_id = f"{relation_id}:assertion:{row['assertion']}"
            add_node(assertion_id, "assertion", row["assertion"])
            subject_id = None
            if row["subject"] != "unknown":
                subject_id = f"{relation_id}:subject:{row['subject']}"
                add_node(subject_id, "subject", row["subject"])
            for entity in row["entities"]:
                if MEDICATION.fullmatch(entity):
                    entity_type = "medication"
                elif SYMPTOMS.fullmatch(entity):
                    entity_type = "symptom"
                else:
                    entity_type = "condition"
                entity_id = f"{relation_id}:{entity_type}:{entity}"
                add_node(entity_id, entity_type, entity)

                def connect(kind, value, relation_type):
                    value_id = f"{relation_id}:{kind}:{value.casefold()}"
                    add_node(value_id, kind, value)
                    edges.append(
                        RelationshipEdge(
                            from_node_id=entity_id,
                            to_node_id=value_id,
                            relation_type=relation_type,
                            evidence=evidence_model,
                        )
                    )

                if subject_id:
                    edges.append(
                        RelationshipEdge(
                            from_node_id=entity_id,
                            to_node_id=subject_id,
                            relation_type="subject",
                            evidence=evidence_model,
                        )
                    )
                if row["assertion"] == "negated":
                    edges.append(
                        RelationshipEdge(
                            from_node_id=entity_id,
                            to_node_id=assertion_id,
                            relation_type="negation",
                            evidence=evidence_model,
                        )
                    )
                elif row["assertion"] != "affirmed":
                    edges.append(
                        RelationshipEdge(
                            from_node_id=entity_id,
                            to_node_id=assertion_id,
                            relation_type="assertion",
                            evidence=evidence_model,
                        )
                    )
                if entity_type == "medication":
                    for match in QUANTITY.finditer(quote):
                        connect("dose", match.group(), "dose")
                    for match in ROUTE.finditer(quote):
                        route = {
                            "orally": "oral",
                            "by mouth": "oral",
                            "intravenously": "intravenous",
                            "subcutaneously": "subcutaneous",
                            "topically": "topical",
                        }.get(match.group().lower(), match.group().lower())
                        connect("route", route, "route")
                    for match in FREQUENCY.finditer(quote):
                        connect("frequency", match.group().lower(), "frequency")
                    for match in MENTIONED_DURATION.finditer(quote):
                        connect("duration", match.group().lower(), "duration")
                    for match in TIMING.finditer(quote):
                        value = match.group().lower()
                        if FREQUENCY.fullmatch(value) or MENTIONED_DURATION.fullmatch(
                            value
                        ):
                            continue
                        connect("temporality", value, "temporality")
                    for action in row["actions"]:
                        connect("action", action, "action")
                elif entity_type == "symptom":
                    for match in TIMING.finditer(quote):
                        value = match.group().lower()
                        if not FREQUENCY.fullmatch(value):
                            connect("temporality", value, "temporality")
    return {
        "schema_version": "explicit_relationship_graph_v2",
        "relations": rows,
        "nodes": [node.model_dump(mode="json") for node in nodes.values()],
        "edges": [edge.model_dump(mode="json") for edge in edges],
        "limitations": [
            "Limited explicit vocabulary; unrecognized terms are not validated.",
            "Unknown subjects and ambiguous scope require human review.",
            "No relation is an approved clinical fact.",
        ],
        "clinical_calibration": False,
    }


def validate_graph(graph, transcript):
    """Check source binding and graph integrity before application use."""
    if not isinstance(graph, dict) or graph.get("schema_version") != (
        "explicit_relationship_graph_v2"
    ):
        raise ValueError("clinical_relationship_schema_invalid")
    segment_by_id = {
        str(segment["segment_id"]): segment for segment in transcript["segments"]
    }
    nodes = [RelationshipNode.model_validate(node) for node in graph.get("nodes", [])]
    node_ids = [node.node_id for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("clinical_relationship_node_duplicate")
    node_id_set = set(node_ids)
    rows = [
        ClinicalRelationship.model_validate(row) for row in graph.get("relations", [])
    ]
    source_spans = set()
    for row in rows:
        evidence = row.evidence
        segment = segment_by_id.get(str(evidence.segment_id))
        if (
            segment is None
            or evidence.end_char > len(segment["text"])
            or segment["text"][evidence.start_char : evidence.end_char]
            != evidence.quote
            or not row.review_required
        ):
            raise ValueError("clinical_relationship_evidence_invalid")
        source_spans.add(
            (
                str(evidence.segment_id),
                evidence.start_char,
                evidence.end_char,
                evidence.quote,
            )
        )
    edges = [RelationshipEdge.model_validate(edge) for edge in graph.get("edges", [])]
    seen_edges = set()
    for edge in edges:
        evidence = edge.evidence
        segment = segment_by_id.get(str(evidence.segment_id))
        edge_key = (edge.from_node_id, edge.to_node_id, edge.relation_type)
        span_key = (
            str(evidence.segment_id),
            evidence.start_char,
            evidence.end_char,
            evidence.quote,
        )
        if edge_key in seen_edges:
            raise ValueError("clinical_relationship_edge_duplicate")
        if (
            edge.from_node_id not in node_id_set
            or edge.to_node_id not in node_id_set
            or not edge.review_required
            or span_key not in source_spans
            or segment is None
            or evidence.end_char > len(segment["text"])
            or segment["text"][evidence.start_char : evidence.end_char]
            != evidence.quote
        ):
            raise ValueError("clinical_relationship_edge_invalid")
        seen_edges.add(edge_key)
    return {
        "status": "valid",
        "nodes": len(nodes),
        "edges": len(edges),
        "relations": len(rows),
        "all_review_required": True,
        "clinical_calibration": False,
    }
