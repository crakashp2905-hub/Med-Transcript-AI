"""Immutable, source-bound evidence receipts for ASR candidate comparison."""

import json
import re
from copy import deepcopy
from pathlib import Path

from services.canonical import content_sha256

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _candidate(value):
    if not isinstance(value, dict):
        raise ValueError("candidate_record_required")
    if set(value) != {
        "candidate_id",
        "text",
        "backend_id",
        "profile_sha256",
        "decoder_config_sha256",
    }:
        raise ValueError("candidate_fields_invalid")
    if (
        not isinstance(value.get("candidate_id"), str)
        or not value["candidate_id"].strip()
    ):
        raise ValueError("candidate_id_required")
    if not isinstance(value.get("text"), str):
        raise ValueError("candidate_text_required")
    if not isinstance(value.get("backend_id"), str) or not value["backend_id"].strip():
        raise ValueError("candidate_backend_required")
    if _SHA256.fullmatch(value.get("profile_sha256", "")) is None:
        raise ValueError("candidate_profile_digest_required")
    if _SHA256.fullmatch(value.get("decoder_config_sha256", "")) is None:
        raise ValueError("candidate_decoder_digest_required")
    return deepcopy(value)


def create_candidate_receipt(
    *,
    audio_asset_id,
    audio_sha256,
    start_ms,
    end_ms,
    source_transcript_version,
    source_transcript_sha256,
    original_hypothesis,
    alternatives,
    selection_policy_id,
    selection_policy_version,
    selected_candidate_id=None,
    abstained=False,
    abstention_reason=None,
):
    if not isinstance(audio_asset_id, str) or not audio_asset_id.strip():
        raise ValueError("source_audio_id_required")
    if _SHA256.fullmatch(audio_sha256 or "") is None:
        raise ValueError("source_audio_digest_required")
    if (
        type(start_ms) is not int
        or type(end_ms) is not int
        or not 0 <= start_ms < end_ms
    ):
        raise ValueError("invalid_candidate_span")
    if not isinstance(source_transcript_version, str) or not source_transcript_version:
        raise ValueError("source_transcript_version_required")
    if _SHA256.fullmatch(source_transcript_sha256 or "") is None:
        raise ValueError("source_transcript_digest_required")
    if not isinstance(selection_policy_id, str) or not selection_policy_id:
        raise ValueError("selection_policy_id_required")
    if not isinstance(selection_policy_version, str) or not selection_policy_version:
        raise ValueError("selection_policy_version_required")
    if not isinstance(alternatives, list) or len(alternatives) > 8:
        raise ValueError("candidate_alternatives_invalid")
    original = _candidate(original_hypothesis)
    candidate_rows = [original, *(_candidate(value) for value in alternatives)]
    candidate_ids = [row["candidate_id"] for row in candidate_rows]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate_ids_must_be_unique")
    if selected_candidate_id is not None and selected_candidate_id not in candidate_ids:
        raise ValueError("selected_candidate_not_in_receipt")
    if type(abstained) is not bool:
        raise ValueError("abstention_state_invalid")
    if abstained and (
        selected_candidate_id is not None
        or not isinstance(abstention_reason, str)
        or not abstention_reason.strip()
    ):
        raise ValueError("abstention_requires_reason_and_no_selection")
    if not abstained and abstention_reason is not None:
        raise ValueError("abstention_reason_without_abstention")
    payload = {
        "schema_version": "asr_candidate_receipt_v1",
        "audio_asset_id": audio_asset_id,
        "audio_sha256": audio_sha256,
        "span": {"start_ms": start_ms, "end_ms": end_ms},
        "source_transcript_version": source_transcript_version,
        "source_transcript_sha256": source_transcript_sha256,
        "original_hypothesis": original,
        "alternatives": candidate_rows[1:],
        "selection_policy": {
            "policy_id": selection_policy_id,
            "version": selection_policy_version,
        },
        "selected_candidate_id": selected_candidate_id,
        "abstained": abstained,
        "abstention_reason": abstention_reason,
        "review_required": True,
        "adopted": False,
        "clinical_truth_verified": False,
    }
    payload["receipt_sha256"] = content_sha256(payload)
    return payload


def write_candidate_receipt(path, receipt):
    if not isinstance(receipt, dict) or not isinstance(
        receipt.get("receipt_sha256"), str
    ):
        raise ValueError("candidate_receipt_invalid")
    body = deepcopy(receipt)
    digest = body.pop("receipt_sha256")
    if content_sha256(body) != digest:
        raise ValueError("candidate_receipt_digest_mismatch")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return destination
