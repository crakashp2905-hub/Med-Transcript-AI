"""Canonical provenance envelope for derived artifacts.

The envelope is deliberately explicit: missing provenance is invalid rather
than silently inferred. Clinical release authorization is never granted by
this helper.
"""

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
