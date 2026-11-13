import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
import pytest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from services.api.ingest import run_once
from services.api.main import create_app
from services.api.storage import Store
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


def test_approval_idempotency_replays_same_decision_and_rejects_changed_request(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    note = draft(client, eid, tx, facts)["note"]
    route = f"/v1/encounters/{eid}/approvals"
    request = {
        "note_version_id": note["id"],
        "expected_note_sha256": note["sha256"],
        "verification_report_id": note["verification_report_id"],
        "patient_identifiers_reconfirmed": True,
    }
    request_headers = headers()
    first = client.post(route, json=request, headers=request_headers)
    assert first.status_code == 201, first.text
    replayed = client.post(route, json=request, headers=request_headers)
    assert replayed.status_code == 201
    assert replayed.json() == first.json()
    incompatible = {**request, "note_version_id": str(uuid4())}
    assert (
        client.post(route, json=incompatible, headers=request_headers).status_code
        == 409
    )
    independently_retried = client.post(route, json=request, headers=headers())
    assert independently_retried.status_code == 201
    assert independently_retried.json()["id"] == first.json()["id"]
    with Store(path).transaction() as con:
        assert (
            con.execute(
                "SELECT COUNT(*) FROM approvals WHERE note=?", (note["id"],)
            ).fetchone()[0]
            == 1
        )


def test_full_review_approval_export_and_amendment(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)

    def lifecycle():
        with Store(path).transaction() as con:
            return con.execute(
                "SELECT stage,version FROM encounter_lifecycle WHERE encounter=?",
                (eid,),
            ).fetchone()

    assert lifecycle()["stage"] == "transcribed"
    result = draft(client, eid, tx, facts)
    assert lifecycle()["stage"] == "verified"
    statement = next(
        item for section in result["note"]["sections"] for item in section["statements"]
    )
    assert statement["source_version_id"] == tx["id"]
    assert statement["evidence"]["quote"] == statement["text"]
    source_citation = (
        f"[Source: transcript {statement['source_version_id']}; "
        f"segment {statement['evidence']['segment_id']}; "
        f"characters {statement['evidence']['start_char']}-"
        f"{statement['evidence']['end_char']}; quote SHA-256 "
        f"{hashlib.sha256(statement['evidence']['quote'].encode('utf-8')).hexdigest()}.]"
    )
    assert result["verification"]["gate"] == "ready"
    approved = approve(client, eid, result["note"])
    assert approved.status_code == 201, approved.text
    assert lifecycle()["stage"] == "approved"
    assert approve(client, eid, result["note"]).json() == approved.json()
    with Store(path).transaction() as con:
        assert (
            con.execute(
                "SELECT COUNT(*) FROM approvals WHERE note=?",
                (result["note"]["id"],),
            ).fetchone()[0]
            == 1
        )
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
        if format in ("markdown", "text"):
            assert source_citation in downloaded.text
        elif format == "json":
            serialized = downloaded.json()["note"]["sections"]
            exported_statement = next(
                row
                for section in serialized
                for row in section["statements"]
                if row["statement_id"] == statement["statement_id"]
            )
            assert exported_statement["origin"] == "source_linked"
            assert exported_statement["evidence"] == statement["evidence"]
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
    assert lifecycle()["stage"] == "verified"
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
    import services.review.routers.exports as exports

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
        old_rules.setattr(exports, "findings_for", lambda note, source: [])
        result = draft(client, eid, tx, facts)
        assert result["verification"]["gate"] == "ready"
        approval = approve(client, eid, result["note"])
        assert approval.status_code == 201
        historical_export = client.post(
            f"/v1/encounters/{eid}/exports",
            headers=headers(),
            json={"approval_id": approval.json()["id"], "format": "json"},
        )
        assert historical_export.status_code == 201
    before = client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()
    assert before["verification"]["validator_version"] == "rules_v2"
    assert before["approval"]["id"] == approval.json()["id"]
    recheck = before["current_safety_recheck"]
    assert recheck["gate"] == "blocked"
    assert any(
        item["code"] == "dose_or_unit_disagreement" for item in recheck["findings"]
    )
    quarantined = client.get(
        historical_export.json()["download_url"], headers=headers()
    )
    assert (
        quarantined.status_code == 409
        and quarantined.json()["code"] == "current_safety_review_required"
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


def test_speaker_role_correction_requires_authorization_and_invalidates_approval(setup):
    client, path, _ = setup
    eid, source, facts = prepare(client, path)
    note = draft(client, eid, source, facts)["note"]
    route = f"/v1/encounters/{eid}/transcripts/{source['id']}"
    segment = source["segments"][0]
    request = {
        "segments": [
            {
                "segment_id": segment["segment_id"],
                "start_ms": segment["start_ms"],
                "end_ms": segment["end_ms"],
                "text": segment["text"],
                "role": "clinician",
            }
        ],
        "correction_reason": "Correct the reviewed synthetic speaker attribution.",
        "english_confirmed": True,
        "source_completeness_reviewed": True,
        "source_review_reason": "Reviewed the full synthetic source interval.",
    }
    with Store(path).transaction() as con:
        authorization_id = con.execute(
            "SELECT id FROM authorizations WHERE encounter=? AND withdrawn_at IS NULL",
            (eid,),
        ).fetchone()["id"]
    authorization_route = f"/v1/encounters/{eid}/authorizations/{authorization_id}/withdraw"
    assert client.post(authorization_route, headers=headers()).status_code == 200
    denied = client.patch(
        route,
        headers={**headers(), "If-Match": f'"{source["sha256"]}"'},
        json=request,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "authorization_required"

    renewed = client.post(
        f"/v1/encounters/{eid}/authorizations",
        headers=headers(),
        json={
            "scopes": ["recording", "local_processing"],
            "policy_version": "synthetic-v1",
            "method": "verbal_documented",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )
    assert renewed.status_code == 201, renewed.text
    corrected = client.patch(
        route,
        headers={**headers(), "If-Match": f'"{source["sha256"]}"'},
        json=request,
    )
    assert corrected.status_code == 201, corrected.text
    assert corrected.json()["segments"][0]["role"] == "clinician"
    assert corrected.json()["segments"][0]["role_status"] == "human_confirmed"
    assert approve(client, eid, note).status_code == 412
    assert client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).json()["stale"] is True


def test_speaker_turn_split_merge_keeps_source_interval_and_immutable_lineage(setup):
    client, path, _ = setup
    eid, source, _ = prepare(client, path)
    original = source["segments"][0]
    route = f"/v1/encounters/{eid}/transcripts/{source['id']}"
    split_at = (original["start_ms"] + original["end_ms"]) // 2
    split = client.patch(
        route,
        headers={**headers(), "If-Match": f'"{source["sha256"]}"'},
        json={
            "segments": [
                {
                    "parent_segment_ids": [original["segment_id"]],
                    "start_ms": original["start_ms"],
                    "end_ms": split_at,
                    "text": "Patient reports cough",
                    "role": "patient",
                },
                {
                    "parent_segment_ids": [original["segment_id"]],
                    "start_ms": split_at,
                    "end_ms": original["end_ms"],
                    "text": "and denies fever.",
                    "role": "patient",
                },
            ],
            "correction_reason": "Split and reviewed synthetic speaker turns.",
            "english_confirmed": True,
            "source_completeness_reviewed": True,
            "source_review_reason": "Reviewed the complete synthetic recording.",
        },
    )
    assert split.status_code == 201, split.text
    split_tx = split.json()
    assert split_tx["parent_version_id"] == source["id"]
    assert [s["correction_kind"] for s in split_tx["segments"]] == [
        "split_child",
        "split_child",
    ]
    assert all(
        s["parent_segment_ids"] == [original["segment_id"]]
        for s in split_tx["segments"]
    )
    assert (
        split_tx["segments"][0]["end_ms"]
        == split_tx["segments"][1]["start_ms"]
        == split_at
    )

    merged = client.patch(
        f"/v1/encounters/{eid}/transcripts/{split_tx['id']}",
        headers={**headers(), "If-Match": f'"{split_tx["sha256"]}"'},
        json={
            "segments": [
                {
                    "parent_segment_ids": [
                        s["segment_id"] for s in split_tx["segments"]
                    ],
                    "start_ms": original["start_ms"],
                    "end_ms": original["end_ms"],
                    "text": "Patient reports cough and denies fever.",
                    "role": "patient",
                }
            ],
            "correction_reason": "Merge and review synthetic speaker turns.",
            "english_confirmed": True,
            "source_completeness_reviewed": True,
            "source_review_reason": "Reviewed the complete synthetic recording.",
        },
    )
    assert merged.status_code == 201, merged.text
    merged_tx = merged.json()
    assert merged_tx["parent_version_id"] == split_tx["id"]
    assert merged_tx["segments"][0]["correction_kind"] == "merged_turn"
    assert merged_tx["segments"][0]["parent_segment_ids"] == [
        s["segment_id"] for s in split_tx["segments"]
    ]
    assert client.get(route, headers=headers()).json()["segments"] == source["segments"]


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
