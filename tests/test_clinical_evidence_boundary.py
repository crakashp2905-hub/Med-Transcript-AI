import json
from pathlib import Path


def test_clinical_claims_remain_unestimated_until_required_external_evidence():
    path = Path("evaluation/contracts/clinical-evidence-boundary-v1.json")
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["clinical_release_authorized"] is False
    assert set(body["claims"]) == {
        "clinical_sensitivity",
        "clinician_productivity_improvement",
        "clinical_safety",
    }
    for claim in body["claims"].values():
        assert claim["estimable"] is False
        assert claim["estimate"] is None
        assert claim["required_evidence"]
    assert "unknown, not zero risk" in body["interpretation"]
