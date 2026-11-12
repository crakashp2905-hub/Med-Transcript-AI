import hashlib
import sqlite3
import pytest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from services.api.ingest import run_once
from services.api.main import create_app
from tests.test_foundation import headers, queue_upload


def prepare(client, path, text="Patient reports cough and denies fever.", assets=None):
    eid, upload, _, _ = queue_upload(client)
    assert (
        run_once(path, assets or str(Path(path).parent / "assets"))["status"]
        == "succeeded"
    )
    response = client.post(
        f"/v1/encounters/{eid}/manual-transcripts",
        headers=headers(),
        json={
            "audio_asset_id": upload["id"],
            "segments": [
                {"start_ms": 0, "end_ms": 100, "text": text, "role": "patient"}
            ],
            "english_confirmed": True,
            "source_completeness_reviewed": True,
            "source_review_reason": "Complete synthetic source reviewed for this test.",
        },
    )
    assert response.status_code == 201, response.text
    facts = client.get(f"/v1/encounters/{eid}/facts", headers=headers()).json()["facts"]
    for fact in facts:
        fact.update(
            reviewed=True,
            critical_reviewed=True,
            subject="family" if fact["subject"] == "family" else "patient",
            temporality="current"
            if fact["temporality"] == "unknown"
            else fact["temporality"],
        )
    return eid, response.json(), facts


def draft(client, eid, tx, facts):
    response = client.post(
        f"/v1/encounters/{eid}/drafts",
        headers=headers(),
        json={"transcript_version_id": tx["id"], "facts": facts},
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve(client, eid, note):
    return client.post(
        f"/v1/encounters/{eid}/approvals",
        headers=headers(),
        json={
            "note_version_id": note["id"],
            "expected_note_sha256": note["sha256"],
            "verification_report_id": note["verification_report_id"],
            "patient_identifiers_reconfirmed": True,
        },
    )


def test_full_review_approval_export_and_amendment(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    result = draft(client, eid, tx, facts)
    statement = next(
        item for section in result["note"]["sections"] for item in section["statements"]
    )
    assert statement["source_version_id"] == tx["id"]
    assert statement["evidence"]["quote"] == statement["text"]
    assert result["verification"]["gate"] == "ready"
    approved = approve(client, eid, result["note"])
    assert approved.status_code == 201, approved.text
    assert approve(client, eid, result["note"]).json() == approved.json()
    for format in ("markdown", "text", "json"):
        response = client.post(
            f"/v1/encounters/{eid}/exports",
            headers=headers(),
            json={"approval_id": approved.json()["id"], "format": format},
        )
        assert response.status_code == 201
        receipt = response.json()
        assert len(receipt["evidence_graph_sha256"]) == 64
        downloaded = client.get(receipt["download_url"], headers=headers())
        assert downloaded.status_code == 200
        assert (
            downloaded.headers["x-evidence-graph-sha256"]
            == receipt["evidence_graph_sha256"]
        )
        assert hashlib.sha256(downloaded.content).hexdigest() == receipt["sha256"]
        assert "approved" in downloaded.text.lower()
    blocked = client.patch(
        f"/v1/encounters/{eid}/notes/{result['note']['id']}",
        headers={**headers(), "If-Match": f'"{result["note"]["sha256"]}"'},
        json={"transcript_version_id": tx["id"], "facts": facts},
    )
    assert blocked.status_code == 409
    amendment = client.post(
        f"/v1/encounters/{eid}/amendments",
        headers=headers(),
        json={
            "approval_id": approved.json()["id"],
            "reason": "Add a clinician-authored clarification to the record.",
        },
    )
    assert amendment.status_code == 201
    assert amendment.json()["note"]["parent_version_id"] == result["note"]["id"]
    assert approve(client, eid, result["note"]).status_code == 412


def test_ambiguous_medication_blocks_and_correction_creates_new_version(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path, "I take metformin 500 or 850 mg.")
    facts[0]["category"] = "medication"
    result = draft(client, eid, tx, facts)
    assert approve(client, eid, result["note"]).status_code == 409
    finding = next(
        item
        for item in result["verification"]["findings"]
        if item["code"] == "ambiguous_statement"
    )
    response = client.post(
        f"/v1/encounters/{eid}/findings/{finding['finding_id']}/resolve",
        headers=headers(),
        json={
            "expected_note_sha256": result["note"]["sha256"],
            "fact_id": facts[0]["fact_id"],
            "action": "clinician_correction",
            "corrected_text": "Patient takes metformin 500 mg.",
            "reason": "Clinician confirmed the dose directly against the medication label.",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["note"]["id"] != result["note"]["id"]
    assert response.json()["verification"]["gate"] == "ready"
    corrected = response.json()["note"]["facts"]
    assert corrected[0]["excluded"] is True
    assert corrected[0]["text"] == corrected[0]["evidence"]["quote"]
    assert any(
        fact["origin"] == "clinician_entered"
        and fact["evidence"] is None
        and "500 mg" in fact["text"]
        for fact in corrected
    )
    assert (
        client.get(
            f"/v1/encounters/{eid}/notes/{result['note']['id']}", headers=headers()
        ).json()["facts"][0]["excluded"]
        is False
    )
    assert approve(client, eid, response.json()["note"]).status_code == 201


@pytest.mark.parametrize(
    "source,claim,expected",
    [
        (
            "Maybe the patient takes warfarin 0.5 mg daily.",
            "Patient takes warfarin 5 mg daily.",
            "dose_or_unit_disagreement",
        ),
        (
            "Maybe the patient takes warfarin 0.5 mg daily.",
            "Patient takes insulin 0.5 mg daily.",
            "medication_or_allergen_disagreement",
        ),
        (
            "Maybe the patient denies fever.",
            "Patient reports fever.",
            "negation_disagreement",
        ),
    ],
)
def test_ambiguous_source_cannot_clear_critical_contradiction(
    setup, source, claim, expected
):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path, source)
    assert len(facts) == 1
    facts[0].update(
        text=claim,
        clarification="Clinician independently checked this claim against a separate source.",
    )
    result = draft(client, eid, tx, facts)
    assert result["verification"]["gate"] == "blocked"
    warning = next(
        item for item in result["verification"]["findings"] if item["code"] == expected
    )
    assert warning["severity"] == "critical" and warning["validator_version"]
    assert (
        warning["source_reference"]["quote_sha256"]
        == hashlib.sha256(facts[0]["evidence"]["quote"].encode()).hexdigest()
    )
    assert warning["mismatch_fields"]
    assert approve(client, eid, result["note"]).status_code == 409


def test_legacy_approval_is_preserved_but_new_export_rechecks_current_rules(
    setup, monkeypatch
):
    import services.review.service as service
    import services.review.routers.approvals as approvals

    client, path, _ = setup
    eid, tx, facts = prepare(
        client, path, "Maybe the patient takes warfarin 0.5 mg daily."
    )
    facts[0].update(
        text="Patient takes warfarin 5 mg daily.",
        clarification="A programmatic clarification simulates the old unsafe approval path.",
    )
    with monkeypatch.context() as old_rules:
        old_rules.setattr(service, "RULES_VERSION", "rules_v2")
        old_rules.setattr(service, "findings_for", lambda note, source: [])
        old_rules.setattr(approvals, "findings_for", lambda note, source: [])
        result = draft(client, eid, tx, facts)
        assert result["verification"]["gate"] == "ready"
        approval = approve(client, eid, result["note"])
        assert approval.status_code == 201
    before = client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()
    assert before["verification"]["validator_version"] == "rules_v2"
    assert before["approval"]["id"] == approval.json()["id"]
    recheck = before["current_safety_recheck"]
    assert recheck["gate"] == "blocked"
    assert any(
        item["code"] == "dose_or_unit_disagreement" for item in recheck["findings"]
    )
    export = client.post(
        f"/v1/encounters/{eid}/exports",
        headers=headers(),
        json={"approval_id": approval.json()["id"], "format": "json"},
    )
    assert (
        export.status_code == 409
        and export.json()["code"] == "current_safety_review_required"
    )
    after = client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()
    assert after["verification"] == before["verification"]
    assert after["approval"] == before["approval"]


def test_false_or_cross_version_evidence_is_rejected(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    facts[0]["evidence"]["quote"] = "Invented normal examination."
    assert (
        client.post(
            f"/v1/encounters/{eid}/drafts",
            headers=headers(),
            json={"transcript_version_id": tx["id"], "facts": facts},
        ).status_code
        == 422
    )
    facts[0]["evidence"]["segment_id"] = str(uuid4())
    assert (
        client.post(
            f"/v1/encounters/{eid}/drafts",
            headers=headers(),
            json={"transcript_version_id": tx["id"], "facts": facts},
        ).status_code
        == 422
    )


def test_transcript_edit_invalidates_old_note_approval_and_preserves_original(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    note = draft(client, eid, tx, facts)["note"]
    body = {
        "segments": [
            {
                "segment_id": tx["segments"][0]["segment_id"],
                "text": "Patient denies cough.",
                "role": "patient",
            }
        ],
        "correction_reason": "Correct the synthetic negation example.",
        "english_confirmed": True,
        "source_completeness_reviewed": True,
        "source_review_reason": "Entire source recording checked again.",
    }
    route = f"/v1/encounters/{eid}/transcripts/{tx['id']}"
    edited = client.patch(
        route, headers={**headers(), "If-Match": f'"{tx["sha256"]}"'}, json=body
    )
    assert edited.status_code == 201
    assert approve(client, eid, note).status_code == 412
    assert (
        client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()["stale"]
        is True
    )
    assert (
        client.patch(
            route, headers={**headers(), "If-Match": f'"{tx["sha256"]}"'}, json=body
        ).status_code
        == 412
    )
    assert (
        client.get(route, headers=headers()).json()["segments"][0]["text"]
        != edited.json()["segments"][0]["text"]
    )


def test_review_resources_are_tenant_and_clinician_scoped(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    result = draft(client, eid, tx, facts)
    approval = approve(client, eid, result["note"]).json()
    receipt = client.post(
        f"/v1/encounters/{eid}/exports",
        headers=headers(),
        json={"approval_id": approval["id"], "format": "json"},
    ).json()
    for token in ("b" * 40, "c" * 40):
        for route in (
            f"/v1/encounters/{eid}/workspace",
            f"/v1/encounters/{eid}/notes/{result['note']['id']}",
            receipt["download_url"],
            f"/v1/encounters/{eid}/audit",
        ):
            assert client.get(route, headers=headers(token)).status_code == 404


def test_unreviewed_facts_and_invented_clinician_citation_block(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    facts[0]["reviewed"] = False
    result = draft(client, eid, tx, facts)
    assert approve(client, eid, result["note"]).status_code == 409
    facts[0].update(
        origin="clinician_entered",
        clarification="Clinician added an independent examination finding.",
    )
    assert (
        client.post(
            f"/v1/encounters/{eid}/drafts",
            headers=headers(),
            json={"transcript_version_id": tx["id"], "facts": facts},
        ).status_code
        == 422
    )


def test_concurrent_approval_retries_create_one_approval(setup):
    client, path, tokens = setup
    eid, tx, facts = prepare(client, path)
    note = draft(client, eid, tx, facts)["note"]

    def request(_):
        with TestClient(create_app(path, tokens)) as other:
            return approve(other, eid, note)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(request, range(3)))
    assert all(response.status_code == 201 for response in results)
    assert len({response.json()["id"] for response in results}) == 1
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 1


def test_deletion_tombstones_access_and_blocks_processing(setup):
    client, path, _ = setup
    eid, tx, _ = prepare(client, path)
    assert (
        client.post(
            f"/v1/encounters/{eid}/deletion-requests", headers=headers()
        ).status_code
        == 202
    )
    assert (
        client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).status_code
        == 404
    )
    from services.api.storage import Store, processing_allowed

    with Store(path).transaction() as con:
        assert processing_allowed(con, eid) is False
