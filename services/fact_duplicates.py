"""Detect duplicate facts without deleting contradictions or temporal variants."""


def detect(facts):
    groups = {}
    for fact in facts:
        key = (fact.get("category"), fact.get("concept"), fact.get("text", "").lower())
        groups.setdefault(key, []).append(fact)
    duplicates = [rows for rows in groups.values() if len(rows) > 1]
    return {
        "groups": duplicates,
        "count": sum(len(rows) - 1 for rows in duplicates),
        "preserved_facts": len(facts),
        "contradictions_retained": True,
    }
