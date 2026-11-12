from pathlib import Path


def test_reproducibility_appendix_covers_required_sections():
    text = Path("docs/reproducibility-appendix.md").read_text().lower()
    for section in (
        "method",
        "experimental protocol",
        "limitations",
        "failure taxonomy",
        "artifacts",
    ):
        assert section in text
