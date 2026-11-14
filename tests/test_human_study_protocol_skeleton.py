import json
from pathlib import Path


def test_future_human_study_protocol_has_no_fabricated_results_or_approval():
    path = Path("evaluation/protocols/decide-ai-human-study-skeleton-v1.json")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    results = protocol["outcomes_and_analysis"]
    assert results["participant_results"] is None
    assert results["participant_level_results"] == []
    assert results["aggregate_results"] is None
    assert protocol["participants"]["status"] == "not_recruited"
    assert protocol["safety_and_governance"]["clinical_release_authorized"] is False
    guidance = protocol["guidance_basis"]
    assert guidance["local_checklist_available"] is False
    assert guidance["exact_item_level_alignment_verified"] is False
    assert protocol["status"] == "draft_not_for_recruitment"
