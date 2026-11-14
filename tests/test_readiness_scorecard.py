import json

import pytest

from services.master_matrix import LEDGER
from services.readiness_scorecard import build


def test_scorecard_keeps_three_weighted_axes_separate_and_bound_to_ledger():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    result = build(ledger, source_commit="a" * 40)

    assert result["clinical_release_authorized"] is False
    assert set(result["axes"]) == {"research", "engineering", "product"}
    assert sum(axis["task_count"] for axis in result["axes"].values()) == 369
    assert all(
        0 <= axis["weighted_readiness_percent"] <= 100
        for axis in result["axes"].values()
    )
    assert result["weighting"]["priority"] == {"P0": 3, "P1": 2, "P2": 1}
    assert result["weighting"]["status_credit"]["verified"] == 1.0
    assert result["weighting"]["status_credit"]["implemented"] == 0.5


def test_scorecard_rejects_unclassified_or_invalid_task_state():
    minimal = {
        "total": 1,
        "tasks": [
            {
                "id": "T-1",
                "section": "99 — unknown",
                "priority": "P0",
                "status": "verified",
            }
        ],
    }
    with pytest.raises(ValueError, match="readiness_section_unclassified"):
        build(minimal, source_commit="b" * 40)

    minimal["tasks"][0]["section"] = "18 — release"
    minimal["tasks"][0]["status"] = "optimistic"
    with pytest.raises(ValueError, match="readiness_task_state_invalid"):
        build(minimal, source_commit="b" * 40)
