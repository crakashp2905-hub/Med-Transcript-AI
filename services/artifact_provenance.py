"""Canonical provenance envelope for derived artifacts.

The envelope is deliberately explicit: missing provenance is invalid rather
than silently inferred. Clinical release authorization is never granted by
this helper.
"""

import hashlib
import json

REQUIRED = (
    "source_commit",
    "dataset_sha",
    "code_sha",
    "model_digest",
    "config_digest",
    "created_at",
    "status",
    "limitations",
    "validation_scope",
)


def make_provenance(**values):
    missing = [key for key in REQUIRED if not values.get(key)]
    if missing:
        raise ValueError("provenance_missing:" + ",".join(missing))
    result = {key: values[key] for key in REQUIRED}
    result["real_patient_release_authorized"] = False
    return result


def validate_provenance(value):
    if not isinstance(value, dict):
        raise ValueError("provenance_not_object")
    missing = [key for key in REQUIRED if not value.get(key)]
    if missing:
        raise ValueError("provenance_missing:" + ",".join(missing))
    if value.get("real_patient_release_authorized") is not False:
        raise ValueError("clinical_release_must_remain_false")
    return True


def acceptance_artifact_provenance(
    *,
    source_commit,
    dataset_manifests,
    code_sha,
    config_hashes,
    created_at,
    status,
    limitations,
):
    """Create the canonical envelope used by offline acceptance outputs."""

    def digest(value):
        canonical = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    return make_provenance(
        source_commit=source_commit,
        dataset_sha=digest(dataset_manifests),
        code_sha=code_sha or "unavailable",
        model_digest="not_used_by_offline_acceptance_workflow",
        config_digest=digest(config_hashes),
        created_at=created_at,
        status=status,
        limitations=limitations,
        validation_scope="developer_synthetic_oracles",
    )
