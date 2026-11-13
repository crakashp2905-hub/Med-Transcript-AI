import pytest

from services.clinical_metrics import evaluate, evaluate_cases


def test_synthetic_fact_evaluation_reports_precision_recall_and_omissions():
    gold = [
        {
            "category": "symptom",
            "concept": "cough",
            "subject": "patient",
            "assertion": "affirmed",
            "temporality": "current",
        },
        {
            "category": "medication",
            "concept": "warfarin",
            "subject": "patient",
            "assertion": "affirmed",
            "temporality": "current",
        },
    ]
    observed = [gold[0]]
    result = evaluate("Cough; warfarin.", "Cough.", gold, observed)
    assert result["concept_precision"] == 1.0 and result["concept_recall"] == 0.5
    assert result["concept_omissions"] == 1
    assert result["clinical_adjudication"] == "not_established_by_automated_metrics"


def test_case_metrics_report_micro_macro_and_failure_inclusive_critical_misses():
    medication = {
        "category": "medication",
        "concept": "warfarin",
        "subject": "patient",
        "assertion": "affirmed",
        "temporality": "current",
    }
    cough = {
        "category": "symptom",
        "concept": "cough",
        "subject": "patient",
        "assertion": "affirmed",
        "temporality": "current",
    }
    fever = {
        "category": "symptom",
        "concept": "fever",
        "subject": "patient",
        "assertion": "affirmed",
        "temporality": "current",
    }
    allergy = {
        "category": "allergy",
        "concept": "penicillin",
        "subject": "patient",
        "assertion": "affirmed",
        "temporality": "current",
    }
    result = evaluate_cases(
        [
            {
                "case_id": "partial",
                "reference": "Warfarin and cough.",
                "hypothesis": "Warfarin.",
                "expected": [medication, cough],
                "observed": [medication],
            },
            {
                "case_id": "insertion",
                "reference": "Fever.",
                "hypothesis": "Fever and penicillin allergy.",
                "expected": [fever],
                "observed": [fever, allergy],
            },
            {
                "case_id": "failed",
                "reference": "Warfarin.",
                "hypothesis": "Warfarin.",
                "expected": [medication],
                "observed": [medication],
                "failed": True,
            },
        ],
        critical_categories=["medication", "allergy"],
    )

    assert result["micro"]["true_positive"] == 2
    assert result["micro"]["false_positive"] == 1
    assert result["micro"]["false_negative"] == 2
    assert result["micro"]["precision"] == pytest.approx(2 / 3)
    assert result["micro"]["recall"] == 0.5
    assert result["micro"]["f1"] == pytest.approx(4 / 7)
    assert result["critical_false_negative_count"] == 1
    assert result["macro_case"]["defined_case_count"] == 3
    assert result["macro_case"]["precision"] == 0.5
    assert result["macro_case"]["recall"] == 0.5
    assert result["macro_case"]["f1"] == pytest.approx(4 / 9)
    assert result["clinical_adjudication"] == "not_established_by_automated_metrics"
    assert result["primary_endpoint_unchanged"] == (
        "failure_inclusive_normalized_word_error_rate"
    )


def test_critical_categories_must_be_explicit():
    from services.clinical_metrics import evaluate_cases

    with pytest.raises(ValueError, match="critical_categories_must_be_explicit"):
        evaluate_cases(
            [{"case_id": "empty", "expected": [], "observed": []}],
            critical_categories=None,
        )
