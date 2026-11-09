import pytest

from services.data_provenance import classify


def test_data_provenance_distinguishes_development_and_synthetic_oracles():
    assert classify('dev-audio', predeclared=True)['optimization_allowed'] is True
    assert classify('oracle-1', synthetic_oracle=True)['optimization_allowed'] is False


def test_data_provenance_rejects_ambiguous_labels():
    with pytest.raises(ValueError):
        classify('x', predeclared=True, synthetic_oracle=True)
