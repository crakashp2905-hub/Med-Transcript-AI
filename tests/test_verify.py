from services.verify import (
    ROOT,
    run_verification,
    safe_pytest_diagnostics,
    verification_steps,
)


def test_safe_pytest_diagnostics_excludes_parameter_payload_and_assertion_text():
    output = """FAILED tests/test_example.py::test_case[private fixture payload] - assertion includes source text
ERROR tests/test_example.py::test_setup - sensitive setup traceback
tests/test_example.py:42: AssertionError: private source sentence
================== 1 failed, 12 passed in 0.50s =================="""
    assert safe_pytest_diagnostics(output) == {
        "summary": "1 failed, 12 passed",
        "failed_tests": ["tests/test_example.py::test_case"],
        "error_tests": ["tests/test_example.py::test_setup"],
        "failure_locations": [
            {
                "file": "tests/test_example.py",
                "line": 42,
                "error_type": "AssertionError",
            }
        ],
    }


def test_verification_plan_orders_quality_checks_before_tests_and_frontend():
    steps = verification_steps()
    assert [name for name, _, _ in steps] == [
        "python_format",
        "python_lint",
        "python_types",
        "python_tests",
        "frontend_build",
    ]
    assert steps[-1][2] == ROOT / "apps/clinician-web"


def test_python_only_plan_stops_after_tests():
    assert [name for name, _, _ in verification_steps(python_only=True)] == [
        "python_format",
        "python_lint",
        "python_types",
        "python_tests",
    ]


def test_verification_fails_fast_in_dependency_order(capsys):
    calls = []

    class Result:
        def __init__(self, returncode):
            self.returncode = returncode

    def runner(command, *, cwd, check, capture_output, text):
        assert capture_output is True and text is True
        calls.append((command, cwd, check))
        return Result(1 if len(calls) == 2 else 0)

    result = run_verification(python_only=True, runner=runner)
    assert [entry["check"] for entry in result] == ["python_format", "python_lint"]
    assert result[-1]["status"] == "fail"
    assert len(calls) == 2
