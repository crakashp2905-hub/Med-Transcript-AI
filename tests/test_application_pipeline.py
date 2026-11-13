from uuid import uuid4

from services.application_pipeline import enrich_fact_proposal
from services.review.relationships import analyze_transcript
from tests.test_foundation import headers
from tests.test_review_workflow import prepare
import sqlite3


def test_application_pipeline_uses_resource_graph_attribution_and_relationship_helpers():
    fact_id = str(uuid4())
    segment_id = str(uuid4())
    text = "Patient denies left knee pain"
    transcript = {
        "id": str(uuid4()),
        "audio_asset_id": str(uuid4()),
        "segments": [{"segment_id": segment_id, "text": text}],
    }
    result = enrich_fact_proposal(
        transcript=transcript,
        facts=[
            {
                "fact_id": fact_id,
                "text": text,
                "evidence": {
                    "segment_id": segment_id,
                    "start_char": 0,
                    "end_char": len(text),
                    "quote": text,
                },
            }
        ],
        relationships=analyze_transcript(transcript),
    )
    assert result["application_pipeline"] == "source_validated_clinical_review_v2"
    assert result["attribution"][0]["assertion"] == "negated"
    assert result["evidence_graph"]["complete_to_fact"] is True
    assert result["evidence_graph"]["complete_to_export"] is False
    assert result["relationship_graph_validation"]["status"] == "valid"
    assert result["relationship_graph_validation"]["edges"] > 0


def test_family_history_subject_is_derived_from_text_not_a_diarized_speaker_hint():
    fact_id = str(uuid4())
    segment_id = str(uuid4())
    text = "My sister has diabetes."
    transcript = {
        "id": str(uuid4()),
        "audio_asset_id": str(uuid4()),
        "segments": [{"segment_id": segment_id, "text": text}],
    }
    result = enrich_fact_proposal(
        transcript=transcript,
        facts=[
            {
                "fact_id": fact_id,
                "text": text,
                "speaker_role": "clinician",
                "evidence": {
                    "segment_id": segment_id,
                    "start_char": 0,
                    "end_char": len(text),
                    "quote": text,
                },
            }
        ],
        relationships=analyze_transcript(transcript),
    )

    attribution = result["attribution"][0]
    assert attribution["subject"] == "family"
    assert attribution["subject_attribution_source"] == "utterance_content_only"
    assert attribution["diarization_role_used_for_subject"] is False


def test_fact_proposal_http_persists_graph_and_real_clinical_relationships(setup):
    client, path, _ = setup
    eid, tx, _ = prepare(
        client, path, "Taking warfarin 2.5 mg orally once daily. Patient denies fever."
    )
    url = f"/v1/encounters/{eid}/fact-proposals"
    response = client.post(
        url, headers=headers(), json={"transcript_version_id": tx["id"]}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    enriched = body["application_enrichment"]
    assert body["clinical_state_snapshot"]["schema_version"] == (
        "clinical_state_snapshot_v1"
    )
    assert body["clinical_state_comparison"]["status"] == (
        "baseline_snapshot_no_comparable_prior"
    )
    assert body["clinical_state_snapshot"]["approval_authority"] is False
    assert body["source_relationships"]["schema_version"] == (
        "explicit_relationship_graph_v2"
    )
    assert enriched["relationship_graph_validation"]["status"] == "valid"
    assert enriched["relationship_graph_validation"]["edges"] > 0
    assert enriched["evidence_graph"]["edges"][0]["from"] == tx["audio_asset_id"]
    assert enriched["evidence_graph"]["facts_checked"] == len(body["facts"])
    assert enriched["relation_validation"]["all_valid"]
    rows = enriched["relation_validation"]["relations"]
    assert any(
        "warfarin" in r["entities"] and r["quantities"] and r["routes"] == ["oral"]
        for r in rows
    )
    assert any("fever" in r["entities"] and r["assertion"] == "negated" for r in rows)
    saved = client.get(
        f"/v1/encounters/{eid}/clinical-proposals/{body['id']}", headers=headers()
    )
    assert (
        saved.status_code == 200 and saved.json()["application_enrichment"] == enriched
    )
    assert all(not f["reviewed"] for f in body["facts"])


def test_successive_application_transcript_proposals_surface_state_contradiction(setup):
    client, path, _ = setup
    eid, first_tx, _ = prepare(client, path, "Patient reports fever.")
    first_response = client.post(
        f"/v1/encounters/{eid}/fact-proposals",
        headers=headers(),
        json={"transcript_version_id": first_tx["id"]},
    )
    assert first_response.status_code == 201, first_response.text
    assert first_response.json()["clinical_state_comparison"]["status"] == (
        "baseline_snapshot_no_comparable_prior"
    )

    revision = client.post(
        f"/v1/encounters/{eid}/manual-transcripts",
        headers=headers(),
        json={
            "audio_asset_id": first_tx["audio_asset_id"],
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 100,
                    "text": "Patient denies fever.",
                    "role": "patient",
                }
            ],
            "english_confirmed": True,
            "source_completeness_reviewed": True,
            "source_review_reason": "Corrected synthetic source for state comparison.",
        },
    )
    assert revision.status_code == 201, revision.text
    second_response = client.post(
        f"/v1/encounters/{eid}/fact-proposals",
        headers=headers(),
        json={"transcript_version_id": revision.json()["id"]},
    )
    assert second_response.status_code == 201, second_response.text
    comparison = second_response.json()["clinical_state_comparison"]
    assert comparison["status"] == "review_required"
    assert any(
        change["change"] == "potential_contradiction"
        and change["severity"] == "critical"
        and change["requires_clinician_review"]
        for change in comparison["changes"]
    )
    assert comparison["approval_authority"] is False


def test_fact_proposal_rejects_fabricated_evidence_before_persistence(
    setup, monkeypatch
):
    from services.review.clinical_models import RuleExtractor

    client, path, _ = setup
    eid, tx, _ = prepare(client, path, "Taking warfarin 2.5 mg.")
    original = RuleExtractor.extract_facts

    def bad(self, transcript, **kwargs):
        result = original(self, transcript, **kwargs)
        result["facts"][0]["evidence"]["quote"] = "fabricated"
        return result

    monkeypatch.setattr(RuleExtractor, "extract_facts", bad)
    response = client.post(
        f"/v1/encounters/{eid}/fact-proposals",
        headers=headers(),
        json={"transcript_version_id": tx["id"]},
    )
    assert response.status_code == 422
    with sqlite3.connect(path) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) FROM model_proposals WHERE kind='fact_proposal'"
            ).fetchone()[0]
            == 0
        )


def test_memory_budget_blocks_model_before_provider_is_called(setup, monkeypatch):
    client, path, _ = setup
    eid, tx, _ = prepare(client, path, "Patient denies fever.")

    class Provider:
        def extract_facts(self, *args, **kwargs):
            raise AssertionError("must not run under memory pressure")

    client.app.state.clinical_models = Provider()
    monkeypatch.setenv("MED_TRANSCRIPT_LOCAL_MEMORY_BYTES", "1")
    response = client.post(
        f"/v1/encounters/{eid}/fact-proposals",
        headers=headers(),
        json={"transcript_version_id": tx["id"], "mode": "local_model"},
    )
    assert (
        response.status_code == 503
        and response.json()["code"] == "local_inference_busy"
    )
