"""Validate immutable paired inputs and resource settings for deterministic BECCSV ablations."""

import hashlib
import json
from pathlib import Path

from services.canonical import content_sha256


FEATURES = {
    "source_coverage",
    "temporal_edges",
    "relation_edges",
    "uncertainty_abstention",
    "deterministic_rules",
    "local_verifier",
}
EXPECTED_ARMS = {
    "deterministic_core",
    "no_source_coverage",
    "no_temporal_edges",
    "no_relation_edges",
    "no_uncertainty_abstention",
    "no_deterministic_rules",
}
EXPECTED_DATASETS = {
    "unseen": "evaluation/clinical-challenge-unseen-v1.json",
    "relations": "evaluation/clinical-challenge-relational-v1.json",
    "bindings": "evaluation/clinical-bindings-development-v1.json",
}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_case_bindings(root="."):
    root = Path(root)
    bindings = []
    datasets = []
    for dataset_id, relative_path in EXPECTED_DATASETS.items():
        path = root / relative_path
        raw = path.read_bytes()
        document = json.loads(raw)
        datasets.append(
            {
                "dataset_id": dataset_id,
                "path": relative_path,
                "sha256": content_sha256(document),
                "file_sha256": hashlib.sha256(raw).hexdigest(),
                "annotation_scope": document.get(
                    "scope", document.get("annotation_status", "unlabeled")
                ),
            }
        )
        for case in document.get("cases", []):
            case_id = f"{dataset_id}::{case['id']}"
            expected_unsafe = case.get("expected_unsafe", case.get("unsafe"))
            bindings.append(
                {
                    "case_id": case_id,
                    "dataset_id": dataset_id,
                    "case_sha256": content_sha256(case),
                    "source_text_sha256": content_sha256(case.get("source")),
                    "claim_sha256": content_sha256(case.get("claim")),
                    "expected_unsafe": expected_unsafe,
                }
            )
    return datasets, bindings


def validate_lock(document, root="."):
    if document.get("schema_version") != "beccsv_deterministic_comparison_lock_v1":
        raise ValueError("beccsv_lock_schema_invalid")
    if document.get("status") != "frozen_not_executed":
        raise ValueError("beccsv_lock_execution_status_invalid")
    if document.get("independent_clinical_gold") is not False:
        raise ValueError("beccsv_lock_gold_claim_forbidden")
    if document.get("clinical_release_authorized") is not False:
        raise ValueError("beccsv_lock_release_claim_forbidden")
    datasets, bindings = build_case_bindings(root)
    if document.get("datasets") != datasets:
        raise ValueError("beccsv_lock_dataset_digest_mismatch")
    if document.get("case_bindings") != bindings:
        raise ValueError("beccsv_lock_case_binding_mismatch")
    case_set_sha = content_sha256(bindings)
    if document.get("case_set_sha256") != case_set_sha:
        raise ValueError("beccsv_lock_case_set_digest_mismatch")
    if not bindings or len({row["case_id"] for row in bindings}) != len(bindings):
        raise ValueError("beccsv_lock_case_ids_invalid")

    protocol = document.get("shared_protocol")
    required_protocol_fields = {
        "resource_budget",
        "prompt_policy",
        "retry_policy",
        "model_digests",
    }
    if not isinstance(protocol, dict) or set(protocol) != required_protocol_fields:
        raise ValueError("beccsv_lock_shared_protocol_invalid")
    if protocol["prompt_policy"] != {
        "template_id": "not_used_deterministic_only",
        "length_chars": 0,
        "sha256": None,
    }:
        raise ValueError("beccsv_lock_prompt_policy_changed")
    if protocol["retry_policy"] != {
        "policy_id": "single_attempt_no_retry_v1",
        "attempts_per_case_and_arm": 1,
        "retries": 0,
    }:
        raise ValueError("beccsv_lock_retry_policy_changed")
    if protocol["model_digests"] != {
        "asr": "not_used_fixed_text_inputs",
        "drafting": "not_used",
        "verifier": "not_used_deterministic_only",
    }:
        raise ValueError("beccsv_lock_model_digests_changed")
    budget = protocol["resource_budget"]
    if budget != {
        "max_case_wall_seconds": 10,
        "max_total_wall_seconds_per_arm": 1800,
        "max_parallel_cases": 1,
        "max_parallel_arms": 1,
    }:
        raise ValueError("beccsv_lock_resource_budget_changed")

    arms = document.get("arms")
    if not isinstance(arms, dict) or set(arms) != EXPECTED_ARMS:
        raise ValueError("beccsv_lock_arm_set_invalid")
    core = arms["deterministic_core"]
    core_features = {key: value for key, value in core.items() if key in FEATURES}
    if (
        set(core_features) != FEATURES
        or any(
            value is not True
            for key, value in core_features.items()
            if key != "local_verifier"
        )
        or core["local_verifier"] is not False
    ):
        raise ValueError("beccsv_lock_deterministic_core_invalid")
    for arm_id, feature in (
        ("no_source_coverage", "source_coverage"),
        ("no_temporal_edges", "temporal_edges"),
        ("no_relation_edges", "relation_edges"),
        ("no_uncertainty_abstention", "uncertainty_abstention"),
        ("no_deterministic_rules", "deterministic_rules"),
    ):
        arm = arms[arm_id]
        arm_features = {key: value for key, value in arm.items() if key in FEATURES}
        if (
            set(arm_features) != FEATURES
            or any(
                value is not True
                for key, value in arm_features.items()
                if key not in {feature, "local_verifier"}
            )
            or arm_features[feature] is not False
            or arm_features["local_verifier"] is not False
        ):
            raise ValueError("beccsv_lock_arm_must_remove_one_deterministic_feature")
    protocol_sha = content_sha256(protocol)
    for arm in arms.values():
        if arm.get("shared_protocol_sha256") != protocol_sha:
            raise ValueError("beccsv_lock_arm_protocol_reference_mismatch")
        if arm.get("case_set_sha256") != case_set_sha:
            raise ValueError("beccsv_lock_arm_case_set_reference_mismatch")
    return {
        "status": "valid_frozen_protocol",
        "dataset_count": len(datasets),
        "case_count": len(bindings),
        "arm_count": len(arms),
        "case_set_sha256": case_set_sha,
        "executed": False,
        "model_arms_included": False,
        "clinical_release_authorized": False,
    }


def load_lock(path="evaluation/experiments/beccsv-deterministic-lock-v1.json", root="."):
    return validate_lock(_read(path), root=root)
