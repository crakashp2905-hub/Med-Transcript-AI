import sqlite3
from uuid import uuid4
from services.review.clinical_routes import run_semantic_batches
from tests.test_foundation import headers, setup
from tests.test_review_workflow import prepare, draft


class FakeVerifier:
    def __init__(self, fail_batch=None):
        self.calls = []
        self.fail_batch = fail_batch

    def check_claims(self, claims, *, authorized, synthetic):
        assert authorized and synthetic
        self.calls.append(len(claims))
        if self.fail_batch == len(self.calls):
            raise ValueError("synthetic verifier batch failure")
        return {
            "verdicts": [
                {
                    "fact_id": claim["fact_id"],
                    "label": "supported",
                    "evidence_quote": claim["evidence"],
                    "reason": "Synthetic exact source statement.",
                    "rule_findings": [],
                    "requires_review": False,
                }
                for claim in claims
            ],
            "provenance": {"fixture": "bounded_batch_test"},
        }


def test_semantic_verifier_checks_every_saved_evidence_fact_in_bounded_batches(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path, " ".join(["Patient reports cough."] * 25))
    assert len(facts) == 25
    extra = {
        **facts[0],
        "fact_id": str(uuid4()),
        "text": "Clinician added a separately checked statement.",
        "origin": "clinician_entered",
        "evidence": None,
        "clarification": "Independent synthetic clinician statement for coverage accounting.",
    }
    note = draft(client, eid, tx, [*facts, extra])["note"]
    fake = FakeVerifier()
    client.app.state.clinical_models = fake
    route = f"/v1/encounters/{eid}/semantic-checks"
    complete = client.post(
        route, headers=headers(), json={"note_version_id": note["id"]}
    )
    assert complete.status_code == 201, complete.text
    body = complete.json()
    assert fake.calls == [20, 5] and body["batch_count"] == 2
    assert len(body["verdicts"]) == 25 and len(set(body["checked_fact_ids"])) == 25
    assert body["unchecked_fact_ids"] == [] and body["evidence_linked_fact_count"] == 25
    assert body["total_note_fact_count"] == 26 and body[
        "unverifiable_no_source_fact_ids"
    ] == [extra["fact_id"]]
    assert body["completion_status"] == "complete_evidence_linked_scope"
    assert body["cannot_clear_existing_findings"] is True
    partial = client.post(
        route,
        headers=headers(),
        json={
            "note_version_id": note["id"],
            "fact_ids": [facts[0]["fact_id"], facts[1]["fact_id"]],
        },
    )
    assert (
        partial.status_code == 201
        and partial.json()["completion_status"] == "partial_selected_scope"
    )
    assert len(partial.json()["unchecked_fact_ids"]) == 23
    with sqlite3.connect(path) as con:
        before = con.execute(
            "SELECT COUNT(*) FROM model_proposals WHERE kind='semantic_check'"
        ).fetchone()[0]
    client.app.state.clinical_models = FakeVerifier(fail_batch=2)
    failed = client.post(route, headers=headers(), json={"note_version_id": note["id"]})
    assert (
        failed.status_code == 422
        and failed.json()["code"] == "semantic_check_failed_no_output_admitted"
    )
    with sqlite3.connect(path) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) FROM model_proposals WHERE kind='semantic_check'"
            ).fetchone()[0]
            == before
        )


def test_semantic_batch_merge_rejects_missing_duplicate_or_invented_ids():
    claims = [
        {"fact_id": str(uuid4()), "text": "No fever.", "evidence": "No fever."}
        for _ in range(21)
    ]

    class Bad(FakeVerifier):
        def check_claims(self, claims, *, authorized, synthetic):
            result = super().check_claims(
                claims, authorized=authorized, synthetic=synthetic
            )
            if len(self.calls) == 2:
                result["verdicts"][0]["fact_id"] = str(uuid4())
            return result

    import pytest

    with pytest.raises(ValueError, match="coverage"):
        run_semantic_batches(Bad(), claims)
