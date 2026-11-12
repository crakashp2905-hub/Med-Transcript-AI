from services.anatomy_relations import extract


def test_anatomy_relations_preserve_distinct_left_right_entities():
    result = extract("left knee pain and right shoulder pain")
    assert result["relations"] == [
        {"entity": "knee", "laterality": "left"},
        {"entity": "shoulder", "laterality": "right"},
    ]
    assert result["requires_review"] is False
