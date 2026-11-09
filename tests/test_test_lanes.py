from pathlib import Path


def test_ci_defines_independent_backend_offline_frontend_postgres_and_container_lanes():
    ci = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    audit = Path('.github/workflows/dependency-audit.yml').read_text(encoding='utf-8')
    model = Path('.github/workflows/model-inference.yml').read_text(encoding='utf-8')
    for marker in ('test:', 'frontend:', 'postgres:', 'container:', 'MED_TRANSCRIPT_OFFLINE'):
        assert marker in ci
    assert 'pip-audit' in audit and 'model' in model.lower()
