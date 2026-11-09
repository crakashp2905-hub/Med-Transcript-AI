from services.method_comparison import METHODS, compare


def test_method_comparison_requires_identical_case_coverage():
    cases = ['c1', 'c2']
    result = compare(cases, {method: [0, 1] for method in METHODS})
    assert set(result['methods']) == set(METHODS)
    assert result['clinical_sensitivity_claim'] is False
