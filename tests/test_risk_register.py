from pathlib import Path


def test_risk_register_covers_all_eight_required_failure_classes():
    document = Path("docs/product/risk-register.md").read_text(encoding="utf-8")
    for risk_id in range(1, 9):
        assert f"R-{risk_id:02d}" in document
    for phrase in (
        "source corruption",
        "clinically important fact",
        "wrong drug",
        "wrong person",
        "Credentials",
        "unapproved or corrupted note",
        "stale approval",
        "deployment exposes",
    ):
        assert phrase.lower() in document.lower()
    assert "Only the master task ledger can record" in document
    assert "authorizes none of them" in document
