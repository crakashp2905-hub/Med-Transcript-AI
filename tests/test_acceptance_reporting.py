from types import SimpleNamespace
from services.offline_acceptance import test_result_summary as summarize_result,source_inventory


def test_acceptance_failure_report_preserves_ids_without_source_or_parameter_text():
    result=SimpleNamespace(returncode=1,stdout='AssertionError: confidential provider content\nFAILED tests/test_guard.py::test_guard[sensitive-case] - private text\n1 failed, 2 passed in 1.00s\n')
    report=summarize_result(result)
    assert report['exit_code']==1
    assert report['failed_test_ids']==['tests/test_guard.py::test_guard']
    assert 'sensitive' not in str(report) and 'confidential' not in str(report) and 'private' not in str(report)
    assert not report['raw_failure_text_included']
    assert 'private' not in str(summarize_result(SimpleNamespace(returncode=1,stdout='private provider payload')))


def test_acceptance_inventory_pins_browser_tests_ci_and_dependency_contracts():
    inventory=source_inventory()
    for path in ('apps/clinician-web/e2e/recovery.spec.ts','.github/workflows/ci.yml','pyproject.toml','evaluation/primary-endpoint-registry-v1.json'):
        assert path in inventory
