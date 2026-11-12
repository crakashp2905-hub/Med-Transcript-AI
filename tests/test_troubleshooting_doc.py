from pathlib import Path


def test_troubleshooting_guide_covers_required_failure_modes():
    text = Path("docs/troubleshooting.md").read_text().lower()
    for phrase in (
        "local model",
        "microphone",
        "disk full",
        "session expired",
        "codec",
        "failed job",
    ):
        assert phrase in text
