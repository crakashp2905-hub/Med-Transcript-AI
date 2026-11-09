from services.verifier_selection import decision


def test_second_verifier_is_excluded_when_combined_policy_does_not_improve():
    result = decision({'a', 'b'}, {'b', 'c'}, {'a', 'b'})
    assert result['distinct_secondary_errors'] == ['c']
    assert result['include_secondary'] is False
    assert result['decision'] == 'remove_redundant_compute'


def test_second_verifier_requires_distinct_errors_and_improvement():
    result = decision({'a', 'b'}, {'b', 'c'}, {'a'})
    assert result['include_secondary'] is True
