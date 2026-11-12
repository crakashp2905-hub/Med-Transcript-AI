from services.accessibility_checklist import REQUIREMENTS, evaluate


def test_accessibility_checklist_surfaces_missing_acceptance_items():
    result = evaluate({key: key == "keyboard_navigation" for key in REQUIREMENTS})
    assert "accessible_labels" in result["failures"]
    assert result["ready"] is False


def test_accessibility_checklist_can_pass_all_items():
    assert evaluate({key: True for key in REQUIREMENTS})["ready"] is True
