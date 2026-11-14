from services.study_dashboard import build


def test_study_dashboard_keeps_failures_visible_and_claims_honest():
    result = build(datasets=["dev"], variants=["deterministic"])
    assert result["visible_failures"] is True
    assert result["cost_claim"] is None and result["accuracy_claim"] is None
    assert result["clinical_productivity_estimate"] is None
    assert result["clinician_time_saved_claim"] is None
    assert result["model_not_admitted_banner"] is True
