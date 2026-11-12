from pathlib import Path


def test_ci_routes_all_direct_pytest_and_verifier_output_through_capture():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    verifier = Path("services/verify.py").read_text(encoding="utf-8")
    coverage = Path("services/module_coverage_report.py").read_text(encoding="utf-8")
    assert "python -m pytest" not in workflow
    assert "python -m services.safe_pytest" in workflow
    assert "capture_output=True" in verifier
    assert "capture_output=True" in coverage


def test_ci_does_not_archive_transcripts_audio_or_unredacted_test_logs():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "actions/upload-artifact" not in workflow
