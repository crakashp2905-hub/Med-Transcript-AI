from pathlib import Path


def test_windows_linux_environment_contract_is_pinned_and_explicit():
    constraints = Path("constraints-ci.txt").read_text(encoding="utf-8")
    runbook = Path("docs/runbooks/ci.md").read_text(encoding="utf-8")
    matrix = Path("docs/runtime-support-matrix.md").read_text(encoding="utf-8")
    assert "Python 3.13" in runbook and "python3.13" in runbook
    assert "Node 22" in runbook and "3.13" in matrix and "constraints" in runbook
    assert "fastapi==" in constraints
