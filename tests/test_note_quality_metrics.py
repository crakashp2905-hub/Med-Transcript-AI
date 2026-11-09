from services.note_quality_metrics import measure


def test_note_quality_metrics_preserve_all_dimensions_and_timeout():
    result = measure(factuality=1, exact_preservation=1, section_correctness=1, length=20, duplication=0, omissions=1, unsafe_claims=0, latency_ms=100, timed_out=True)
    assert result['factuality'] == 1 and result['omissions'] == 1
    assert result['timed_out'] is True and result['clinical_accuracy_claim'] is False
