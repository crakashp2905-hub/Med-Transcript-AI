from pathlib import Path


def test_local_threat_model_covers_end_to_end_product_boundaries_and_limits():
    model = Path("docs/local-threat-model.md").read_text(encoding="utf-8").lower()
    required_boundaries = (
        "browser microphone",
        "live prefixes",
        "api requests",
        "workers / temporary files",
        "prompts and model output",
        "notes / verification / approvals",
        "exports",
        "logs / source / reports",
        "backups and deletion",
    )
    assert all(boundary in model for boundary in required_boundaries)
    assert "clinical release stays `blocked_external_evidence_required`" in model
    assert "not defeated by a local chain" in model
