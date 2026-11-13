from services.beccsv_metamorphic import evaluate


def test_metamorphic_results_keep_false_alarms_and_semantic_flip_findings():
    report = evaluate()
    outcomes = {row["case_id"]: row["outcome"] for row in report["results"]}

    assert report["case_count"] == 7
    assert report["false_alarm_count"] == 2
    assert report["missed_detection_count"] == 0
    assert outcomes == {
        "unit-conversion": "pass",
        "faithful-paraphrase": "false_alarm",
        "clause-order": "false_alarm",
        "temporal-flip": "pass",
        "drug-dose-swap": "pass",
        "negation-reversal": "pass",
        "subject-swap": "pass",
    }
    assert all(
        row["synthetic"] and row["clinical_gold"] is False for row in report["results"]
    )
