from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "docs/product"


def test_product_management_artifacts_are_present_and_cross_linked():
    required = {
        "product-backlog-v1.md": ["P0", "5% normalized-WER", "acceptance evidence"],
        "prioritization-rubric-v1.md": ["not a market score", "Do not combine"],
        "roadmap-v1.md": ["dependency gates", "No phase authorizes real-patient use"],
        "technical-debt-v1.md": ["TD-01", "TD-08", "5% normalized-WER"],
        "risk-register.md": ["Clinical review", "real-patient"],
        "release-notes-v0.4.1.md": [
            "ce57190d56ed587cf237d6d008bbd14f0b71648c",
            "NOT CLINICALLY APPROVED",
        ],
    }
    for name, phrases in required.items():
        content = (PRODUCT / name).read_text(encoding="utf-8")
        assert all(phrase.lower() in content.lower() for phrase in phrases), name

    backlog = (PRODUCT / "product-backlog-v1.md").read_text(encoding="utf-8")
    for artifact in (
        "prioritization-rubric-v1.md",
        "roadmap-v1.md",
        "technical-debt-v1.md",
        "risk-register.md",
    ):
        assert artifact in backlog


def test_product_bundle_keeps_external_validation_as_a_dependency():
    backlog = (PRODUCT / "product-backlog-v1.md").read_text(encoding="utf-8").lower()
    roadmap = (PRODUCT / "roadmap-v1.md").read_text(encoding="utf-8").lower()
    release = (PRODUCT / "release-notes-v0.4.1.md").read_text(encoding="utf-8").lower()
    assert "qualified reviewers" in backlog
    assert "blocked until institution" in roadmap
    assert "not a clinical release" in release
    assert "5% normalized-wer" in release
