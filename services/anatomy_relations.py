"""Conservative anatomy/laterality relation extraction."""

import re


def extract(text):
    entities = re.findall(
        r"\b(?:knee|shoulder|arm|leg|ear|eye|hand|foot)\b", text.lower()
    )
    sides = re.findall(r"\b(?:left|right|bilateral)\b", text.lower())
    relations = []
    for index, entity in enumerate(entities):
        side = sides[index] if index < len(sides) else "unknown"
        relations.append({"entity": entity, "laterality": side})
    return {
        "relations": relations,
        "requires_review": len(entities) != len(sides)
        or len(set(entities)) != len(entities),
    }
