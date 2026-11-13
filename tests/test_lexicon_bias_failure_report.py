import hashlib
import json
from pathlib import Path


def test_hash_bound_lexicon_pilot_preserves_all_local_runtime_failures():
    path = Path("evaluation/reports/asr-lexicon-bias-pilot-v2.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "5d32dbbcedca049b7471877edcb6be97278dace7a0d683b6a7ebe3154e55edfb"
    )
    assert report["status"] == "development_pilot_not_clinical_validation"
    assert report["acceptance_data_used"] is False
    assert report["clinical_gold"] is False
    assert report["candidate_bias_metadata"]["candidate_only"] is True
    assert report["candidate_bias_metadata"]["text_mutation"] is False
    assert len(report["samples"]) == report["paired_sample_count"] == 8

    for arm in ("baseline", "biased"):
        aggregate = report["aggregates"][arm]
        assert aggregate == {
            "positive_term_recall_count": 0,
            "positive_term_recall_denominator": 4,
            "negative_term_false_insertion_count": 0,
            "negative_control_denominator": 4,
            "normalized_edits": 153,
            "reference_words": 153,
            "normalized_wer": 1.0,
            "failures": 8,
        }
        assert all(
            sample["arms"][arm]["failure"] and sample["arms"][arm]["hypothesis"] == ""
            for sample in report["samples"]
        )

    assert all(
        sample["arms"]["biased"]["error_type"] == "ASRFailure"
        for sample in report["samples"]
    )
