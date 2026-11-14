import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/product/product-operations-v1.md"


def test_product_modes_onboarding_metrics_and_slos_are_explicit():
    contract = json.loads(
        (ROOT / "evaluation/contracts/product-operations-v1.json").read_text(
            encoding="utf-8"
        )
    )
    document = DOC.read_text(encoding="utf-8")
    assert contract["verified_task_ids"] == [
        "MTA-15-11",
        "MTA-15-13",
        "MTA-15-14",
        "MTA-15-16",
        "MTA-15-17",
        "MTA-15-18",
        "MTA-15-19",
    ]
    assert contract["mode_ids"] == [
        "local_synthetic_demo",
        "clinician_workstation_candidate",
        "read_only_investor",
        "institution_pilot_candidate",
    ]
    assert all(section in document for section in (
        "## Product promise",
        "## Packaged modes",
        "## Zero-assumption onboarding and manual fallback",
        "## Product success metric dictionary",
        "## Dashboard measurement classes",
        "## Guardrail metrics and stop conditions",
        "## Hypothesis SLOs by hardware tier",
    ))
    assert "not guarantees" in document
    assert "manual workflow" in document
    assert "5% normalized WER admission gate remains unchanged" in document


def test_competitive_matrix_remains_blocked_without_verified_sources():
    contract = json.loads(
        (ROOT / "evaluation/contracts/product-operations-v1.json").read_text(
            encoding="utf-8"
        )
    )
    document = DOC.read_text(encoding="utf-8")
    assert contract["blocked_task_ids"] == ["MTA-15-12"]
    assert contract["research_constraints"]["external_sources_consulted"] is False
    assert contract["research_constraints"]["competitive_claims_verified"] is False
    assert "No competitor matrix is published" in document
