import json
import hashlib
from pathlib import Path

import pytest

from services.clinical_metrics import (
    PRIMARY_ENDPOINT,
    WEIGHTED_VERSION,
    concept_key,
    evaluate,
    surface_form_diagnostics,
)
from services.clinical_evaluation import annotated


def concept(category, name, assertion="affirmed"):
    return {
        "category": category,
        "concept": name,
        "subject": "patient",
        "assertion": assertion,
        "temporality": "current",
    }


def test_weighted_concepts_are_secondary_and_require_external_weights():
    medication = concept("medication", "warfarin")
    negated_fever = concept("negation", "fever", "negated")
    affirmed_fever = concept("symptom", "fever", "affirmed")
    weights = {
        concept_key(medication): 1,
        concept_key(negated_fever): 5,
        concept_key(affirmed_fever): 5,
    }
    report = evaluate(
        "No fever; take warfarin",
        "Fever; take warfarin",
        [medication, negated_fever],
        [medication, affirmed_fever],
        impact_weights=weights,
    )
    assert report["normalized_wer"] == 0.25
    weighted = report["weighted_secondary_endpoint"]
    assert weighted["metric_version"] == WEIGHTED_VERSION
    assert weighted["primary_endpoint_unchanged"] == PRIMARY_ENDPOINT
    assert weighted["weighted_concept_omissions"] == 5
    assert weighted["weighted_concept_insertions"] == 5
    assert weighted["weighted_concept_error_rate"] == pytest.approx(10 / 6)
    assert weighted["weighted_concept_recall"] == pytest.approx(1 / 6)
    assert len(weighted["weight_registry_sha256"]) == 64
    with pytest.raises(ValueError, match="positive_finite"):
        evaluate(
            "No fever",
            "No fever",
            [negated_fever],
            [negated_fever],
            impact_weights={concept_key(negated_fever): float("nan")},
        )


def test_weighted_concepts_keep_failures_failure_inclusive_and_fail_closed():
    gold = concept("dose", "0.5 mg")
    report = evaluate(
        "Take 0.5 mg",
        "Take 0.5 mg",
        [gold],
        [gold],
        failed=True,
        impact_weights={concept_key(gold): 3},
    )
    assert report["failed"] is True
    assert report["reference_words"] == 3
    assert report["normalized_wer"] == 1
    assert report["weighted_secondary_endpoint"]["weighted_concept_omissions"] == 3
    assert report["weighted_secondary_endpoint"]["weighted_concept_recall"] == 0
    with pytest.raises(ValueError, match="cover_exact_concepts"):
        evaluate("take dose", "", [gold], [], impact_weights={"{}": 1})


def test_annotated_runner_binds_frozen_secondary_endpoint_registry(tmp_path):
    source = tmp_path / "annotations.json"
    gold = concept("symptom", "fever")
    source.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "synthetic-case",
                        "reference": "Fever",
                        "hypothesis": "Fever",
                        "expected": [gold],
                        "observed": [gold],
                        "impact_weights": {concept_key(gold): 2},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = annotated(source)
    registry = json.loads(
        Path("evaluation/clinical-asr-secondary-endpoints-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["cases"][0]["normalized_wer"] == 0
    assert (
        report["cases"][0]["weighted_secondary_endpoint"]["primary_endpoint_unchanged"]
        == registry["primary_endpoint"]["id"]
    )
    assert report["secondary_endpoint_registry_sha256"]
    assert (
        report["secondary_endpoint_registry_sha256"]
        == hashlib.sha256(
            Path("evaluation/clinical-asr-secondary-endpoints-v1.json").read_bytes()
        ).hexdigest()
    )
    assert registry["clinical_gold_available_in_repository"] is False


def test_surface_diagnostics_separate_case_and_punctuation_without_changing_wer():
    report = evaluate("NO, fever!", "no fever.", [], [])
    details = report["surface_form_diagnostics"]
    assert report["normalized_wer"] == 0
    assert report["normalized_edits"] == 0
    assert report["raw_edits"] == 2
    assert details["aligned_normalized_words"] == 2
    assert details["case_mismatches"] == 1
    assert details["case_mismatch_rate"] == 0.5
    assert details["punctuation_boundaries_compared"] == 3
    assert details["punctuation_boundary_mismatches"] == 2
    assert details["lexical_endpoint_unchanged"] == PRIMARY_ENDPOINT


def test_surface_diagnostics_leave_unaligned_punctuation_unscored():
    details = surface_form_diagnostics("No symptom", "No severe symptom")
    assert details["aligned_normalized_words"] == 2
    assert details["punctuation_boundaries_compared"] == 2
    assert details["punctuation_boundary_mismatch_rate"] == 0
