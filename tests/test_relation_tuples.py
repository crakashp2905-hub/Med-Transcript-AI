from services.relation_tuples import RELATIONS, validate


def test_relation_tuples_cover_required_clinical_categories():
    result = validate(
        [{"type": relation, "evidence": "synthetic#1"} for relation in RELATIONS]
    )
    assert result["all_valid"] is True
    assert len(result["relations"]) == 5
