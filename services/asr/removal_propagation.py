"""Fail-closed removal propagation for future ASR correction artifacts.

This rebuild helper never edits immutable inputs or claims to erase learned
weights. Any model artifact whose training lineage intersects a revoked source
is invalidated and must be rebuilt from the sanitized manifest.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def source_reference_id(*, dataset_id: str, record_id: str, reference_sha256: str) -> str:
    """Return a stable opaque identifier for one source reference record."""
    if not dataset_id or not record_id or not _SHA256.fullmatch(reference_sha256):
        raise ValueError("source_reference_identity_invalid")
    payload = {
        "dataset_id": dataset_id,
        "record_id": record_id,
        "reference_sha256": reference_sha256,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_source_ids(source_ids: object) -> set[str]:
    if not isinstance(source_ids, list) or any(
        not isinstance(value, str) or not _SHA256.fullmatch(value)
        for value in source_ids
    ):
        raise ValueError("source_lineage_invalid")
    return set(source_ids)


def rebuild_after_revocation(
    *,
    lexicon: dict,
    retraining_manifest: dict,
    revoked_source_ids: list[str],
) -> dict:
    """Remove revoked source rows and invalidate every dependent model build.

    Expected retraining manifest keys are ``records`` (each row has a list of
    ``source_ids``) and optional ``artifacts`` (each descriptor has an
    ``artifact_id`` and ``source_ids``). Inputs are copied and never mutated.
    The returned receipt contains hashes and counts, not the revoked IDs.
    """
    revoked = _validate_source_ids(revoked_source_ids)
    if not revoked:
        raise ValueError("revocation_set_empty")
    if not isinstance(lexicon, dict) or not isinstance(lexicon.get("entries"), list):
        raise ValueError("lexicon_schema_invalid")
    if not isinstance(retraining_manifest, dict) or not isinstance(
        retraining_manifest.get("records"), list
    ):
        raise ValueError("retraining_manifest_schema_invalid")

    rebuilt_lexicon = copy.deepcopy(lexicon)
    removed_occurrences = 0
    surviving_entries = []
    for entry in rebuilt_lexicon["entries"]:
        provenance = entry.get("provenance")
        if not isinstance(provenance, list):
            raise ValueError("lexicon_provenance_invalid")
        surviving = []
        for row in provenance:
            if not isinstance(row, dict):
                raise ValueError("lexicon_provenance_invalid")
            source_id = source_reference_id(
                dataset_id=row.get("dataset_id", ""),
                record_id=row.get("record_id", ""),
                reference_sha256=row.get("reference_sha256", ""),
            )
            if source_id in revoked:
                removed_occurrences += 1
            else:
                surviving.append(row)
        if surviving:
            entry["provenance"] = surviving
            surviving_entries.append(entry)
    rebuilt_lexicon["entries"] = surviving_entries
    allowed_terms = {entry.get("term") for entry in surviving_entries}
    if "candidate_terms" in rebuilt_lexicon:
        rebuilt_lexicon["candidate_terms"] = [
            term for term in rebuilt_lexicon["candidate_terms"] if term in allowed_terms
        ]

    rebuilt_manifest = copy.deepcopy(retraining_manifest)
    retained_records = []
    removed_records = 0
    for row in rebuilt_manifest["records"]:
        if not isinstance(row, dict):
            raise ValueError("retraining_record_invalid")
        if _validate_source_ids(row.get("source_ids")) & revoked:
            removed_records += 1
        else:
            retained_records.append(row)
    rebuilt_manifest["records"] = retained_records

    artifacts = rebuilt_manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("retraining_artifacts_invalid")
    retained_artifacts = []
    invalidated_artifact_ids = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(
            artifact.get("artifact_id"), str
        ):
            raise ValueError("retraining_artifact_invalid")
        if _validate_source_ids(artifact.get("source_ids")) & revoked:
            invalidated_artifact_ids.append(artifact["artifact_id"])
        else:
            retained_artifacts.append(artifact)
    rebuilt_manifest["artifacts"] = retained_artifacts

    return {
        "schema_version": "asr_revocation_rebuild_receipt_v1",
        "status": "rebuild_required" if invalidated_artifact_ids else "rebuilt",
        "input_lexicon_sha256": _digest(lexicon),
        "output_lexicon_sha256": _digest(rebuilt_lexicon),
        "input_manifest_sha256": _digest(retraining_manifest),
        "output_manifest_sha256": _digest(rebuilt_manifest),
        "revocation_set_sha256": _digest(sorted(revoked)),
        "revoked_source_count": len(revoked),
        "removed_lexicon_occurrences": removed_occurrences,
        "removed_lexicon_terms": len(lexicon["entries"]) - len(surviving_entries),
        "removed_training_records": removed_records,
        "invalidated_artifact_ids": sorted(invalidated_artifact_ids),
        "revoked_sources_referenced": False,
        "learned_weights_erased": False,
        "retraining_required": bool(invalidated_artifact_ids),
        "rebuilt_lexicon": rebuilt_lexicon,
        "rebuilt_manifest": rebuilt_manifest,
    }
