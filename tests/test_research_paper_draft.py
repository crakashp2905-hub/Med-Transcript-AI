import json
from pathlib import Path


def test_manuscript_has_required_sections_and_reconciles_negative_results():
    root = Path(__file__).resolve().parents[1]
    paper = (
        root / "docs/research/med-transcript-engineering-paper-draft-v0.1.md"
    ).read_text(encoding="utf-8")
    required = (
        "Motivation and intended use",
        "Related work and scope of claims",
        "System and method",
        "Experimental setup",
        "Baselines and planned verification comparisons",
        "Results and negative findings",
        "Threats to validity and limitations",
        "Reproducibility and data availability",
    )
    assert all(heading in paper for heading in required)
    assert "systematic related-work search has not been completed" in paper
    assert "No evaluated local configuration meets the 5% gate" in paper
    publication = json.loads(
        (root / "evaluation/publications/mta-17-03-benchmark-tables-v1.json").read_text(
            encoding="utf-8"
        )
    )
    for row in publication["report"]["models"]:
        assert f"{row['normalized_wer']:.2%}" in paper
        assert row["candidate_id"] in publication["generated_markdown"]
    assert "have not been run" in paper
    assert "not clinical false-alarm rates" in paper
    assert (root / "docs/product-architecture.md").is_file()
    assert (root / "evaluation/reproducibility-pack-v3.json").is_file()
