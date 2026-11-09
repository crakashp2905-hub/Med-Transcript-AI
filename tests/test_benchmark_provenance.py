import pytest

from services.benchmark_provenance import validate_run


def test_provenance_retains_failed_partial_and_retry_ancestry():
    report = {'manifest_sha256': 'm', 'complete': False, 'resumed_from': {'path': 'prior.json', 'sha256': 'p'},
              'cases': [{'id': 'one', 'status': 'complete'}, {'id': 'two', 'status': 'failed'}, {'id': 'three', 'status': 'partial'}]}
    value = validate_run(report, expected_manifest_sha256='m')
    assert value['counts'] == {'completed': 1, 'failed': 1, 'partial': 1}
    assert value['complete'] is False and value['retry_ancestry_preserved'] is True
    with pytest.raises(ValueError, match='benchmark_manifest_hash_mismatch'):
        validate_run(report, expected_manifest_sha256='changed')
