from pathlib import Path


def test_architecture_sequence_covers_the_required_clinical_lifecycle_in_order():
    page = Path("docs/product-architecture.md").read_text(encoding="utf-8")
    required = [
        "POST /transcriptions",
        "Append immutable transcript version",
        "POST /fact-proposals",
        "POST /draft-proposals",
        "POST /semantic-checks",
        "PATCH /notes/{id}",
        "POST /approvals",
        "POST /exports",
    ]
    positions = [page.index(marker) for marker in required]
    assert positions == sorted(positions)
    assert "never an approved note" in page
    assert "cannot approve or clear gates" in page
    assert "AI-generated content never replaces" in " ".join(page.split())
