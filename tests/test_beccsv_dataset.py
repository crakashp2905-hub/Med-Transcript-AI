import copy
import json
from pathlib import Path

import pytest

from services.beccsv_dataset import (
    generate_synthetic_scenarios,
    validate_lock,
    validate_manifest,
)


ROOT = Path("evaluation/datasets/beccsv-synthetic-dev-v1")


def _manifest():
    return json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def test_synthetic_beccsv_dataset_is_detailed_and_locked():
    summary = validate_lock(ROOT / "manifest.json", ROOT / "lock.json")
    assert summary == {
        "dataset_id": "beccsv-synthetic-dev-v1",
        "case_count": 8,
        "source_fact_count": 24,
        "note_claim_count": 22,
        "synthetic_only": True,
        "clinical_gold": False,
    }
    assert len({case["case_id"] for case in _manifest()["cases"]}) == 8


def test_scenario_generator_is_repeatable_and_explicitly_synthetic():
    first = generate_synthetic_scenarios()
    second = generate_synthetic_scenarios()
    assert first == second and len(first) == 5
    assert all(case["synthetic"] and not case["clinical_gold"] for case in first)
    assert {case["expected_mismatch"] for case in first} == {
        "relation_mismatch",
        "polarity_mismatch",
        "subject_mismatch",
        "temporal_mismatch",
    }
    for case in first:
        transcript = " ".join(turn["text"] for turn in case["turns"])
        assert case["source_fact"]["quote"] in transcript
        assert case["note_claim"]["source_fact_ids"] == [case["source_fact"]["fact_id"]]


@pytest.mark.parametrize(
    "mutation", ["acceptance", "evidence", "reference", "ids", "mismatch"]
)
def test_synthetic_beccsv_dataset_rejects_scope_or_integrity_changes(mutation):
    manifest = copy.deepcopy(_manifest())
    case = manifest["cases"][0]
    if mutation == "acceptance":
        manifest["acceptance_use_authorized"] = True
    elif mutation == "evidence":
        case["source_facts"][0]["quote"] = "quote not present in transcript"
    elif mutation == "reference":
        case["note_claims"][0]["source_fact_ids"] = ["unknown-fact"]
    elif mutation == "mismatch":
        manifest["cases"][3]["expected_mismatches"][0]["source_fact_ids"] = [
            "unknown-fact"
        ]
    else:
        case["note_claims"][1]["claim_id"] = case["note_claims"][0]["claim_id"]

    with pytest.raises(ValueError):
        validate_manifest(manifest)
