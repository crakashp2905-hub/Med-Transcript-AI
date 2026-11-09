import pytest

from services.metric_validation import validate_metric


def test_metric_validation_enforces_counts_percentages_and_failures():
    report = {'normalized_edits': 2, 'reference_words': 10, 'normalized_wer': .2,
              'failed_samples': 0, 'sample_count': 3, 'complete': True}
    assert validate_metric(report)['complete'] is True
    for changed in ({**report, 'normalized_edits': 11}, {**report, 'normalized_wer': .3}, {**report, 'failed_samples': 4}):
        with pytest.raises(ValueError): validate_metric(changed)


def test_metric_validation_preserves_zero_case_and_hash_mismatch_failures():
    assert validate_metric({'normalized_edits': 0, 'reference_words': 0, 'normalized_wer': None,
                            'failed_samples': 0, 'sample_count': 0})['valid'] is True
    with pytest.raises(ValueError, match='metric_input_hash_mismatch'):
        validate_metric({'normalized_edits': 0, 'reference_words': 0, 'normalized_wer': None,
                         'failed_samples': 0, 'sample_count': 0, 'hash_mismatch': True})
