from pathlib import Path


def test_fixture_policy_explicitly_separates_clinical_gold():
    text = Path('docs/fixture-label-policy.md').read_text(encoding='utf-8')
    assert 'never clinical gold' in text
    assert 'never independent human adjudication' in text
