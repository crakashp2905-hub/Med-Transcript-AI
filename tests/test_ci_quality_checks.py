from pathlib import Path


def test_ci_declares_reproducible_python_typescript_and_offline_checks():
    workflow = Path(".github/workflows/ci.yml").read_text()
    verifier = Path("services/verify.py").read_text()
    assert "ruff==0.15.13" in workflow
    assert "mypy==1.18.2" in workflow
    assert "python -m services.verify --python-only" in workflow
    assert '"ruff", "format", "--check"' in verifier
    assert '"ruff", "check"' in verifier
    assert '"mypy", "services"' in verifier
    assert "npm run build" in workflow
    assert "MED_TRANSCRIPT_OFFLINE: '1'" in workflow
    assert "release-summary:" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
