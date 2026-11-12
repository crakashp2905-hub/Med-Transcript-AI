"""Configurable deterministic note style layer that preserves assertions/evidence."""

STYLES = frozenset({"plain", "concise", "expanded"})


def apply(note, style="plain"):
    if style not in STYLES:
        raise ValueError("unknown_note_style")
    statements = [dict(statement) for statement in note.get("statements", [])]
    return {
        "style": style,
        "statements": statements,
        "source_facts_preserved": True,
        "evidence_preserved": True,
        "semantic_mutation": False,
    }
