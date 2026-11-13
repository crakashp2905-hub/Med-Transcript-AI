"""Validate a preregistered BECCSV ablation matrix without running models."""

import json
from pathlib import Path


FEATURES = {
    "source_coverage",
    "temporal_edges",
    "relation_edges",
    "uncertainty_abstention",
    "deterministic_rules",
    "local_verifier",
}


def validate_matrix(document):
    if document.get("schema_version") != "beccsv_ablation_matrix_v1":
        raise ValueError("beccsv_ablation_schema_invalid")
    if set(document.get("features", [])) != FEATURES:
        raise ValueError("beccsv_ablation_features_invalid")
    variants = document.get("variants")
    if not isinstance(variants, dict) or set(variants) != {
        "full_beccsv",
        "no_source_coverage",
        "no_temporal_edges",
        "no_relation_edges",
        "no_uncertainty_abstention",
        "no_deterministic_rules",
        "no_local_verifier",
    }:
        raise ValueError("beccsv_ablation_variants_invalid")
    full = variants["full_beccsv"]
    if set(full) != FEATURES or any(value is not True for value in full.values()):
        raise ValueError("beccsv_full_policy_invalid")
    for name, feature in (
        ("no_source_coverage", "source_coverage"),
        ("no_temporal_edges", "temporal_edges"),
        ("no_relation_edges", "relation_edges"),
        ("no_uncertainty_abstention", "uncertainty_abstention"),
        ("no_deterministic_rules", "deterministic_rules"),
        ("no_local_verifier", "local_verifier"),
    ):
        arm = variants[name]
        if (
            set(arm) != FEATURES
            or any(value is not True for key, value in arm.items() if key != feature)
            or arm[feature] is not False
        ):
            raise ValueError("beccsv_ablation_must_remove_one_feature")
    if document.get("status") != "declared_not_executed":
        raise ValueError("beccsv_ablation_execution_status_invalid")
    if document.get("clinical_release_authorized") is not False:
        raise ValueError("beccsv_ablation_release_claim_forbidden")
    return {
        "variant_count": len(variants),
        "single_feature_ablations": len(variants) - 1,
        "executed": False,
        "clinical_release_authorized": False,
    }


def load_matrix(path="evaluation/contracts/beccsv-ablation-matrix-v1.json"):
    return validate_matrix(json.loads(Path(path).read_text(encoding="utf-8")))
