import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _contract():
    return json.loads(
        (ROOT / "evaluation/contracts/product-strategy-v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_product_strategy_covers_first_ten_product_management_tasks():
    contract = _contract()
    document = (ROOT / contract["product_document"]).read_text(encoding="utf-8")
    assert contract["task_coverage"] == [f"MTA-15-{i:02d}" for i in range(1, 11)]
    assert contract["status"] == "internal_hypotheses_not_customer_validated"
    assert contract["research_status"] == {
        "customer_interviews": "not_performed",
        "clinical_observation": "not_performed",
        "independent_clinical_review": "not_performed",
        "purchase_intent": "unknown",
        "competitive_claims": "not_evaluated",
    }
    assert contract["clinical_release_authorized"] is False
    assert "## 1. Product requirements and job to be done" in document
    assert "## 2. Explicit non-goals" in document
    assert "## 3. Synthetic personas" in document
    assert "## 4. End-to-end job map" in document
    assert "## 5. Testable problem hypotheses" in document
    assert "## 6. Customer journey" in document
    assert "## 7. User stories" in document
    assert "## 8. Feature inventory" in document
    assert "## 9. Simulated prioritization" in document
    assert "## 10. Risk-adjusted roadmap" in document


def test_user_story_set_has_twenty_given_when_then_acceptance_examples():
    document = (ROOT / "docs/product/product-requirements-v1.md").read_text(
        encoding="utf-8"
    )
    numbered = [
        line
        for line in document.splitlines()
        if line[:1].isdigit() and ". **As " in line
    ]
    assert len(numbered) == 20
    assert all("**Given**" in row and "**when**" in row and "**then**" in row for row in numbered)


def test_prioritization_and_roadmap_remain_explicitly_hypothetical():
    contract = _contract()
    document = (ROOT / contract["product_document"]).read_text(encoding="utf-8")
    assert contract["prioritization"]["inputs_are_hypothetical"] is True
    assert contract["prioritization"]["customer_demand_claimed"] is False
    assert "not market research" in document
    assert "No milestone authorizes real-patient processing." in document
