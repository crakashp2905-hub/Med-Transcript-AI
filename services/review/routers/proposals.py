"""Proposals routes with preserved exact-version review contracts."""
from contextlib import nullcontext
from services.inference_slot import local_inference_slot
import json
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException

from services.asr.profiles import canonical_json, content_sha256
from services.review.engine import validate_evidence


from services.review.providers import JSONProvider, DeterministicProvider
from services.review.models import DraftProposalInput
from services.review.service import ReviewService
from services.domain_contracts import validate_record
from services.proposal_integrity import decode_proposal

def register(app, services: ReviewService):
    database = services.database
    identity = services.identity
    encounter = services.encounter
    audit = services.audit
    require_processing = services.require_processing
    stamp = services.stamp
    get_tx = services.get_tx

    @app.get("/v1/encounters/{eid}/draft-proposals/{did}")
    def get_draft_proposal(eid: UUID, did: UUID, actor=Depends(identity)):
        with database() as con:
            row = encounter(con,eid,actor)
            proposal = con.execute("SELECT * FROM model_proposals WHERE encounter=? AND id=? AND kind='draft_proposal'",(str(eid),str(did))).fetchone()
            if proposal is None:
                raise HTTPException(404,"draft_proposal_not_found")
            value = decode_proposal(con,proposal,eid)
            value["stale"] = row["current_transcript"] != value["transcript_version_id"]
            return value

    @app.post("/v1/encounters/{eid}/draft-proposals", status_code=201)
    def draft_proposal(eid: UUID, body: DraftProposalInput, actor=Depends(identity)):
        from services.api.storage import active_scopes
        provider = app.state.drafting_provider
        hosted = isinstance(provider, JSONProvider) and provider.mode == "hosted"
        with database() as con:
            row = encounter(con, eid, actor)
            require_processing(con, eid)
            if row["current_transcript"] != str(body.transcript_version_id):
                raise HTTPException(412, "stale_transcript")
            tr, tx = get_tx(con, eid, body.transcript_version_id)
            validate_evidence(body.facts, tx)
            original_hash = tr["sha256"]
            if hosted and (not body.hosted_text_disclosure_accepted or json.loads(row["body"])["requested_inference_mode"] != "hybrid_text" or "hosted_text_processing" not in active_scopes(con,eid)):
                raise HTTPException(422, "hosted_text_disclosure_and_scope_required")
        try:
            with (local_inference_slot() if isinstance(provider,JSONProvider) and provider.mode=='local' else nullcontext(True)) as ready:
                if not ready:raise HTTPException(503,'local_inference_busy')
                result = provider.draft([f.model_dump(mode="json") for f in body.facts], authorized=True, synthetic=True)
            result['deterministic_baseline'] = DeterministicProvider().draft(
                [f.model_dump(mode='json') for f in body.facts], authorized=True, synthetic=True)
        except ValueError:
            raise HTTPException(422, "draft_proposal_failed_no_output_admitted") from None
        with database() as con:
            row = encounter(con, eid, actor)
            require_processing(con, eid)
            if hosted and "hosted_text_processing" not in active_scopes(con,eid):
                raise HTTPException(403, "hosted_text_authorization_withdrawn")
            tr, _ = get_tx(con, eid, body.transcript_version_id)
            if row["current_transcript"] != str(body.transcript_version_id) or tr["sha256"] != original_hash:
                raise HTTPException(412, "stale_transcript")
            did, created = str(uuid4()), stamp()
            version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM model_proposals WHERE encounter=? AND kind='draft_proposal'", (str(eid),)).fetchone()[0]
            result.update(id=did, transcript_version_id=str(body.transcript_version_id), transcript_sha256=original_hash,
                source_facts=[f.model_dump(mode="json") for f in body.facts], status="unreviewed_proposal_not_approvable")
            try:validate_record('draft_proposal',result)
            except ValueError:raise HTTPException(422,'draft_proposal_failed_no_output_admitted') from None
            con.execute("INSERT INTO model_proposals VALUES (?,?,?,?,?,?,?)", (did,str(eid),"draft_proposal",version,content_sha256(result),canonical_json(result),created))
            audit(con, actor, "draft_proposal_created", did)
            return result
