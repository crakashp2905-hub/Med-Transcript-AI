from tests.test_foundation import headers
from tests.test_review_workflow import draft, prepare
from services.canonical import content_sha256
from services.review.engine import directional_coverage


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


def test_detection_receipts_are_per_finding_hash_bound_and_redacted():
    source_secret = "Patient reports a highly private symptom phrase."
    note_secret = "Draft contains sensitive clinical details."
    transcript = {"id": "transcript-1", "segments": [{"text": source_secret}]}
    note = {
        "id": "note-1",
        "facts": [
            {"origin": "source_linked"},
            {"origin": "clinician_entered"},
        ],
    }
    finding = {
        "finding_id": "finding-1",
        "code": "unsupported_claim_terms",
        "severity": "critical",
        "validator_version": "rules_v5",
        "fact_id": "fact-1",
        "message": source_secret + " " + note_secret,
        "source_reference": {
            "transcript_version_id": "transcript-1",
            "segment_id": "segment-1",
            "start_char": 0,
            "end_char": len(source_secret),
            "quote_sha256": "a" * 64,
            "quote": source_secret,
        },
    }

    coverage = directional_coverage(note, transcript, [finding])
    assert coverage["unverifiable_manual_fact_count"] == 1
    receipt = coverage["redacted_detection_receipts"][0]
    digest = receipt["receipt_sha256"]
    receipt_body = {
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    }

    assert digest == content_sha256(receipt_body)
    assert len(coverage["redacted_detection_receipts"]) == 1
    assert source_secret not in str(coverage)
    assert note_secret not in str(coverage)
    assert receipt["raw_source_text_included"] is False
    assert receipt["raw_note_text_included"] is False
    assert receipt["model_prompt_or_completion_included"] is False
    assert receipt["egress_scope"] == "local_tenant_scoped_audit_only"
    assert "quote" not in receipt["source_reference"]
