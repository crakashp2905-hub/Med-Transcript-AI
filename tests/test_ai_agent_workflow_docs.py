from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_instructions_name_protected_inputs_and_safe_test_workflow():
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs/ai-agent-workflow.md").read_text(encoding="utf-8")
    for path in (
        "evaluation/acceptance-reservation-v1.json",
        "evaluation/annotation-source/acceptance-v1/",
        "evaluation/datasets/",
        "evaluation/runs/",
        "evaluation/reports/",
    ):
        assert path in workflow
    for command in (
        "python -m services.master_ledger",
        "python -m services.status_report",
        "python -m services.safe_pytest",
        "python -m ruff check",
        "python -m services.offline_demo --self-test",
    ):
        assert command in workflow
    assert "do not install packages" in workflow.lower()
    assert "Do not run ASR" in workflow
    assert "new versioned report path" in workflow
    assert "Stage only task-specific files" in instructions
    assert "Real-patient processing" in instructions
