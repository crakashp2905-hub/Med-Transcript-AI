from pathlib import Path


def test_browser_fixture_is_never_described_as_observed_clinician_behavior():
    regression = Path("docs/browser-offline-regression.md").read_text(encoding="utf-8")
    operations = Path("docs/product/product-operations-v1.md").read_text(
        encoding="utf-8"
    )
    assert "explicitly scripted adapter" in regression
    assert "not a speech-recognition test, a clinician study" in regression
    assert "simulated" in operations and "clinician_observed" in operations
    assert "Missing values stay null" in operations


def test_study_dashboard_keeps_clinician_productivity_unmeasured():
    from services.study_dashboard import build

    result = build(datasets=[], variants=[])
    assert result["clinical_productivity_estimate"] is None
    assert result["clinician_time_saved_claim"] is None
