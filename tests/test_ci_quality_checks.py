from pathlib import Path


def test_ci_declares_reproducible_python_typescript_and_offline_checks():
    workflow = Path(".github/workflows/ci.yml").read_text()
    assert "ruff==0.15.13" in workflow
    assert "mypy==1.18.2" in workflow
    assert "ruff format --check" in workflow
    assert "ruff check" in workflow
    assert "mypy services" in workflow
    assert "npm run build" in workflow
    assert "MED_TRANSCRIPT_OFFLINE: '1'" in workflow
