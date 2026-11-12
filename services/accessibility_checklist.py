"""Accessibility acceptance checklist for clinician workflows."""

REQUIREMENTS = (
    "keyboard_navigation",
    "accessible_labels",
    "focus_management",
    "screen_reader_status",
    "responsive_layout",
)


def evaluate(checks):
    if not isinstance(checks, dict) or set(checks) != set(REQUIREMENTS):
        raise ValueError("complete_accessibility_checks_required")
    failures = sorted(key for key, value in checks.items() if value is not True)
    return {"checks": checks, "failures": failures, "ready": not failures}
