import json
import base64
from pathlib import Path

from services.clinical_limitations import CLINICAL_LIMITATIONS
from services.model_cards import generate
from services.review.engine import render_export


def test_limitations_match_across_docs_ui_exports_and_model_cards():
    root = Path.cwd()
    surfaces = [
        root / "docs/clinical-limitations.md",
        root / "README.md",
        root / "docs/model-cards.md",
        root / "apps/clinician-web/src/App.tsx",
    ]
    for path in surfaces:
        text = path.read_text(encoding="utf-8")
        for statement in CLINICAL_LIMITATIONS:
            assert statement in text, f"{statement!r} missing from {path}"

    note = {"encounter_id": "demo", "version": 1, "id": "note", "sections": []}
    approval = {"approved_at": "test", "note_sha256": "0" * 64}
    export = json.loads(render_export(note, approval, "json"))
    assert export["limitations"] == list(CLINICAL_LIMITATIONS)
    source = {
        "limitations": list(CLINICAL_LIMITATIONS),
        "transcript_version_id": "transcript",
        "provenance": {},
    }
    assert all(
        statement in render_export(note, approval, "markdown", source=source)
        for statement in CLINICAL_LIMITATIONS
    )
    fhir = json.loads(
        render_export(
            note,
            approval,
            "fhir",
            source=source,
        )
    )
    attachment = json.loads(base64.b64decode(fhir["content"][0]["attachment"]["data"]))
    assert attachment["source"]["limitations"] == list(CLINICAL_LIMITATIONS)
    route = (root / "services/review/routers/exports.py").read_text(encoding="utf-8")
    assert '"limitations": list(CLINICAL_LIMITATIONS)' in route

    cards = generate(root)
    assert all(
        set(CLINICAL_LIMITATIONS) <= set(card["limitations"]) for card in cards["cards"]
    )
