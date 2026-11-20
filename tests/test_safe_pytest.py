from pathlib import Path
from types import SimpleNamespace

from services.safe_pytest import pytest_basetemp, run


def test_pytest_wrapper_logs_only_counts_and_never_payload_or_traceback(capsys):
    secret = "PRIVATE_CLINICAL_FIXTURE_CANARY"
    result = SimpleNamespace(
        returncode=1,
        stdout=f"FAILED test_case.py::test_x[private fixture] - {secret}\n1 failed, 2 passed in 1.0s\n",
        stderr=f"AssertionError: {secret}\n{secret}\n",
    )

    def runner(command, *, capture_output, text, check):
        assert capture_output is True and text is True and check is False
        assert "-m" in command and "pytest" in command
        basetemp = Path(command[command.index("--basetemp") + 1])
        assert basetemp.parent.name == "mta"
        assert len(basetemp.name) == 14
        return result

    assert run(["tests/test_case.py"], runner=runner) == 1
    logged = capsys.readouterr().out
    assert secret not in logged
    assert "AssertionError" not in logged
    assert '"raw_output_logged": false' in logged
    assert "1 failed, 2 passed" in logged
    assert '"failed_tests": ["test_case.py::test_x"]' in logged


def test_safe_pytest_uses_unique_short_temp_directory():
    first = pytest_basetemp()
    second = pytest_basetemp()
    assert first.parent.is_dir()
    assert first.parent.name == "mta"
    assert first != second
    assert len(first.name) == 14
