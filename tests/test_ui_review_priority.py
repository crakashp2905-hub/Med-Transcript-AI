import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_FILES = (
    ROOT / "apps/clinician-web/src/UncertainSpanQueue.tsx",
    ROOT / "apps/clinician-web/src/VerificationWarnings.tsx",
    ROOT / "apps/clinician-web/src/PresentationTools.tsx",
)


def test_review_priority_is_explained_without_uncalibrated_probability_values():
    source = "\n".join(path.read_text(encoding="utf-8") for path in UI_FILES)
    assert "review priorities, not calibrated confidence probabilities" in source
    assert "Review priority reflects explicit source uncertainty and rule severity" in source
    assert not re.search(
        r"(?:confidence|probability)\D{0,20}(?:\d+(?:\.\d+)?\s*%|0\.\d+)",
        source,
        flags=re.IGNORECASE,
    )
