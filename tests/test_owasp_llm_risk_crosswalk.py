import json
from pathlib import Path


def test_owasp_current_llm_risk_crosswalk_is_complete_and_does_not_claim_certification():
    body = json.loads(
        Path("evaluation/contracts/owasp-llm-risk-crosswalk-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert body["framework"] == "OWASP GenAI LLM Top 10 2026"
    assert body["certification_claim"] is False
    assert body["source_url"].startswith("https://genai.owasp.org/")
    assert [risk["id"] for risk in body["risks"]] == [
        f"LLM{i:02}:2026" for i in range(1, 11)
    ]
    for risk in body["risks"]:
        assert risk["name"] and risk["coverage"] in {"partial", "not_applicable"}
        assert risk["evidence"] and risk["gap"]
        assert all(Path(path).is_file() for path in risk["evidence"])
    assert body["risks"][8]["coverage"] == "not_applicable"
