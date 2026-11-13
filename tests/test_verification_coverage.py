from tests.test_foundation import headers
from tests.test_review_workflow import draft, prepare


def test_verification_reports_both_coverage_directions_with_materiality(setup):
    client, path, _ = setup
    eid, tx, extracted = prepare(
        client,
        path,
        "Patient reports cough. Patient reports fever. Taking warfarin 5 mg.",
    )
    selected = [
        dict(fact)
        for fact in extracted
        if fact["text"] in {"Patient reports cough.", "Taking warfarin 5 mg."}
    ]
    medication = next(fact for fact in selected if fact["category"] == "medication")
    medication["text"] = "Taking warfarin 50 mg."
    medication["dose_value"] = "50"

    result = draft(client, eid, tx, selected)
    coverage = result["verification"]["directional_coverage"]

    assert coverage["schema_version"] == "directional_source_note_coverage_v1"
    assert coverage["source_not_in_note"]["status"] == "review_required"
    assert coverage["note_not_in_source"]["status"] == "review_required"
    assert coverage["source_not_in_note"]["by_materiality"]["critical"] > 0
    assert coverage["note_not_in_source"]["by_materiality"]["critical"] > 0
    assert set(coverage["source_not_in_note"]["by_materiality"]) == {
        "critical",
        "major",
        "minor",
    }
    assert set(coverage["note_not_in_source"]["by_materiality"]) == {
        "critical",
        "major",
        "minor",
    }
    assert coverage["raw_source_text_included"] is False
    assert coverage["clinical_adjudication"] == "not_performed"
    assert coverage["approval_authority"] is False
    assert "Patient reports fever" not in str(coverage)
    assert (
        client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()["note"][
            "id"
        ]
        == result["note"]["id"]
    )
