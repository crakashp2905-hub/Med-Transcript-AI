import hashlib
import json
from pathlib import Path


REPORT = Path(
    "evaluation/runs/meddistract-detailed-v7/lexicon-evaluation/"
    "paracetamol-full-cohort-v1.json"
)
SOURCE_RUN = Path("evaluation/runs/meddistract-detailed-v7/matched-ablation-v3.json")
REPORT_SHA256 = "3f195ded6684808120b8a5fdde01286e62fefbcf592db1705e30eaae369e554c"
SOURCE_RUN_SHA256 = "12c074f9029f68f4882aa455b320e05e9c182b0e1928185275942a26e6a702c7"


def test_lexicon_full_cohort_receipt_pins_pairing_and_false_insertion_cost():
    raw = REPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    assert report["schema_version"] == "asr_lexicon_bias_full_cohort_v1"
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["automatic_promotion"] is False
    assert report["inference_executed"] is False
    assert report["model_fit"] is False
    assert report["term"] == "paracetamol"
    assert report["bindings"]["source_run_sha256"] == SOURCE_RUN_SHA256
    assert hashlib.sha256(SOURCE_RUN.read_bytes()).hexdigest() == SOURCE_RUN_SHA256
    assert report["reserved_acceptance_groups_used"] == []
    assert len(report["cases"]) == 32

    baseline = report["summary"]["baseline"]
    biased = report["summary"]["biased"]
    assert baseline["case_count"] == biased["case_count"] == 16
    assert baseline["reference_words"] == biased["reference_words"] == 27366
    assert baseline["certain_positive_term_occurrences"] == 8
    assert baseline["recalled_positive_term_occurrences"] == 2
    assert baseline["positive_occurrence_recall"] == 0.25
    assert biased["recalled_positive_term_occurrences"] == 8
    assert biased["positive_occurrence_recall"] == 1.0
    assert (
        baseline["negative_control_case_count"]
        == biased["negative_control_case_count"]
        == 4
    )
    assert baseline["negative_cases_with_term_in_hypothesis"] == 0
    assert biased["negative_cases_with_term_in_hypothesis"] == 0
    assert (
        baseline["uncertain_only_term_case_count"]
        == biased["uncertain_only_term_case_count"]
        == 4
    )
    assert baseline["uncertain_only_cases_with_term_in_hypothesis"] == 4
    assert biased["uncertain_only_cases_with_term_in_hypothesis"] == 4
    assert baseline["normalized_edits"] == 8445
    assert biased["normalized_edits"] == 11293
    assert baseline["normalized_wer"] > 0.30
    assert biased["normalized_wer"] > 0.41
