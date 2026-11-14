import copy
import json
from pathlib import Path

import pytest

from services.beccsv_experiment_lock import build_case_bindings, validate_lock
from services.canonical import content_sha256


LOCK_PATH = Path("evaluation/experiments/beccsv-deterministic-lock-v1.json")


def _lock():
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def test_beccsv_lock_binds_same_source_facts_cases_and_protocol_across_arms():
    lock = _lock()
    result = validate_lock(lock)
    assert result == {
        "status": "valid_frozen_protocol",
        "dataset_count": 3,
        "case_count": len(build_case_bindings()[1]),
        "arm_count": 6,
        "case_set_sha256": content_sha256(lock["case_bindings"]),
        "executed": False,
        "model_arms_included": False,
        "clinical_release_authorized": False,
    }
    protocol_hash = content_sha256(lock["shared_protocol"])
    for arm in lock["arms"].values():
        assert arm["case_set_sha256"] == lock["case_set_sha256"]
        assert arm["shared_protocol_sha256"] == protocol_hash


@pytest.mark.parametrize(
    ("path", "value", "error"),
    [
        (("shared_protocol", "resource_budget", "max_case_wall_seconds"), 11, "resource_budget"),
        (("shared_protocol", "prompt_policy", "length_chars"), 100, "prompt_policy"),
        (("shared_protocol", "retry_policy", "retries"), 1, "retry_policy"),
        (("shared_protocol", "model_digests", "verifier"), "model-sha256", "model_digests"),
        (("arms", "no_relation_edges", "temporal_edges"), False, "arm_must_remove"),
    ],
)
def test_beccsv_lock_rejects_drift_in_shared_protocol_or_arm(path, value, error):
    lock = copy.deepcopy(_lock())
    cursor = lock
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    if path[0] == "arms":
        lock["arms"]["no_relation_edges"]["shared_protocol_sha256"] = content_sha256(
            lock["shared_protocol"]
        )
    else:
        protocol_hash = content_sha256(lock["shared_protocol"])
        for arm in lock["arms"].values():
            arm["shared_protocol_sha256"] = protocol_hash
    with pytest.raises(ValueError, match=error):
        validate_lock(lock)


def test_beccsv_lock_rejects_changed_case_bindings_and_clinical_claims():
    lock = copy.deepcopy(_lock())
    lock["case_bindings"][0]["source_text_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="case_binding_mismatch"):
        validate_lock(lock)
    lock = _lock()
    lock["independent_clinical_gold"] = True
    with pytest.raises(ValueError, match="gold_claim_forbidden"):
        validate_lock(lock)
