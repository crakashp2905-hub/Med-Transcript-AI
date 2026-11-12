from pathlib import Path
from types import SimpleNamespace
from services.offline_acceptance import (
    PYTEST_ACCEPTANCE_TIMEOUT_SECONDS,
    acceptance_check_status,
    pytest_basetemp,
    test_result_summary as summarize_result,
    source_inventory,
)


def test_acceptance_failure_report_preserves_ids_without_source_or_parameter_text():
    result = SimpleNamespace(
        returncode=1,
        stdout="AssertionError: confidential provider content\nFAILED tests/test_guard.py::test_guard[sensitive-case] - private text\n1 failed, 2 passed in 1.00s\n",
    )
    report = summarize_result(result)
    assert report["exit_code"] == 1
    assert report["failed_test_ids"] == ["tests/test_guard.py::test_guard"]
    assert (
        "sensitive" not in str(report)
        and "confidential" not in str(report)
        and "private" not in str(report)
    )
    assert not report["raw_failure_text_included"]
    assert "private" not in str(
        summarize_result(
            SimpleNamespace(returncode=1, stdout="private provider payload")
        )
    )


def test_acceptance_inventory_pins_browser_tests_ci_and_dependency_contracts():
    inventory = source_inventory()
    for path in (
        "apps/clinician-web/e2e/recovery.spec.ts",
        ".github/workflows/ci.yml",
        "pyproject.toml",
        "evaluation/primary-endpoint-registry-v1.json",
    ):
        assert path in inventory


def test_clean_checkout_bootstraps_isolated_pytest_temp_parent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    temp = pytest_basetemp("clean-checkout")
    assert temp.parent == Path("data")
    assert (tmp_path / temp.parent).is_dir()
    assert not temp.exists()
    assert PYTEST_ACCEPTANCE_TIMEOUT_SECONDS == 1200


def test_acceptance_reports_skip_reasons_and_blocks_critical_skips():
    result = SimpleNamespace(
        returncode=0,
        stdout=(
            "3 passed, 2 skipped in 0.50s\n"
            "SKIPPED [1] tests\\test_media.py:21: could not import 'av': No module named 'av'\n"
            "SKIPPED [1] tests\\test_optional.py:17: optional case disabled\n"
        ),
    )
    report = summarize_result(result)
    assert report["summary"] == "3 passed, 2 skipped in 0.50s"
    assert report["skipped_tests"] == [
        {
            "path": "tests/test_media.py",
            "line": 21,
            "reason_category": "optional_dependency_unavailable",
            "consequence": "tests using this dependency were not executed",
        },
        {
            "path": "tests/test_optional.py",
            "line": 17,
            "reason_category": "pytest_skip_reason_requires_review",
            "consequence": "test behavior was not exercised",
        },
    ]
    assert acceptance_check_status(report) == "fail"
    noncritical = summarize_result(
        SimpleNamespace(returncode=0, stdout="1 passed, 1 skipped in 0.10s\n")
    )
    assert acceptance_check_status(noncritical) == "pass"
    assert "No module named" not in str(report)
