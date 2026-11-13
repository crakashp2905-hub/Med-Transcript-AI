from services.review.clinical import extract
from services.clinical_extraction_comparison import compare_transcript


def transcript():
    return {
        "segments": [
            {
                "segment_id": "s1",
                "role": "patient",
                "text": "No cough.",
            },
            {
                "segment_id": "s2",
                "role": "clinician",
                "text": "Measured blood pressure 120/80 mmHg.",
            },
        ]
    }


class MatchingProvider:
    def __init__(self):
        self.calls = []

    def extract_facts(self, source, *, authorized, synthetic):
        assert authorized and synthetic
        self.calls.append(source)
        facts = extract(source)
        for fact in facts:
            fact["extraction_version"] = "local_model_exact_quote_v1"
        return {
            "facts": facts,
            "findings": [],
            "provenance": {
                "model": "local-test-model",
                "model_digest": "a" * 64,
                "provider_mode": "local",
                "provider_cost_usd": 0,
                "usage": {"total_tokens": 12},
            },
        }


def test_side_by_side_comparison_is_batched_and_reports_provenance_only():
    provider = MatchingProvider()
    result = compare_transcript(
        transcript(),
        case_id="synthetic-case",
        dataset_info={"manifest_sha256": "b" * 64},
        provider=provider,
        batch_size=1,
    )

    assert len(provider.calls) == 2
    assert result["completed_batches"] == 2
    assert result["failed_batches"] == []
    assert result["deterministic_baseline"]["fact_count"] == 2
    assert result["local_qwen_proposal"]["fact_count"] == 2
    assert (
        result["local_qwen_proposal"]["exact_signature_overlap_with_deterministic"] == 2
    )
    assert result["local_qwen_proposal"]["usage_totals"]["total_tokens"] == 24
    assert result["clinical_accuracy"] == "not_established"
    assert "No cough" not in str(result)


def test_comparison_preserves_failed_batches_without_claiming_zero_errors():
    class FailingProvider:
        def extract_facts(self, source, *, authorized, synthetic):
            error = ValueError("safe failure")
            error.code = "clinical_model_timeout"
            raise error

    result = compare_transcript(
        transcript(),
        case_id="synthetic-case",
        dataset_info={"manifest_sha256": "b" * 64},
        provider=FailingProvider(),
        batch_size=1,
    )

    assert result["completed_batches"] == 0
    assert [batch["failure_code"] for batch in result["failed_batches"]] == [
        "clinical_model_timeout",
        "clinical_model_timeout",
    ]
    assert result["local_qwen_proposal"]["fact_count"] == 0
    assert result["local_qwen_proposal"]["invalid_evidence_span_count"] == 0
