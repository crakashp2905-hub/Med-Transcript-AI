import pytest

from services.module_coverage_report import CRITICAL_MODULES, summarize_coverage


def test_coverage_summary_preserves_line_branch_counts_and_source_commit():
    files = {
        path: {
            "summary": {
                "num_statements": 10,
                "covered_lines": 8,
                "percent_covered": 80.0,
                "num_branches": 6,
                "covered_branches": 4,
            }
        }
        for path in CRITICAL_MODULES
    }
    report = summarize_coverage({"files": files}, source_commit="a" * 40)
    assert report["source_commit"] == "a" * 40
    assert report["branch_measurement"] is True
    assert report["modules"][CRITICAL_MODULES[0]]["branch_percent"] == pytest.approx(
        66.67
    )
    assert report["modules"][CRITICAL_MODULES[1]]["line_percent"] == 80.0


def test_coverage_summary_fails_if_a_required_critical_module_is_missing():
    with pytest.raises(ValueError, match="coverage_module_missing"):
        summarize_coverage({"files": {}}, source_commit="b" * 40)
