import pytest

from services.context_effects import record


def test_context_effects_record_quality_and_speed_separately():
    result = record(context_tokens=1024, batch_size=8, omissions=1, hallucinations=0, runtime_seconds=2)
    assert result['omissions'] == 1 and result['hallucinations'] == 0
    assert result['quality_measured'] is True


def test_context_effects_reject_negative_measurements():
    with pytest.raises(ValueError):
        record(context_tokens=-1, batch_size=1, omissions=0, hallucinations=0, runtime_seconds=1)
