import json
from pathlib import Path

from services.unit_economics import estimate


ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "evaluation/protocols/unit-economics-estimate-v1.json"


def test_illustrative_unit_economics_requires_and_labels_assumptions():
    scenario = json.loads(
        (ROOT / "evaluation/protocols/unit-economics-assumptions-v1.json").read_text(
            encoding="utf-8"
        )
    )
    result = estimate(scenario)
    recorded = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    assert result["status"] == "estimated"
    assert result["evidence_status"] == "assumption_only"
    assert result["estimated_cost_per_encounter"] > 0
    assert result["currency_unit"] == "DEMO_CURRENCY_UNIT"
    assert result["clinical_acceptance"] is False
    assert result["clinical_release_authorized"] is False
    assert recorded == result


def test_missing_cost_measurements_return_null_never_default_zero():
    scenario = json.loads(
        (ROOT / "evaluation/protocols/unit-economics-assumptions-v1.json").read_text(
            encoding="utf-8"
        )
    )
    scenario["inputs"]["electricity_price_per_kwh"]["value"] = None

    result = estimate(scenario)

    assert result["status"] == "unavailable"
    assert result["missing_measurements"] == ["electricity_price_per_kwh"]
    assert result["energy_cost_per_encounter"] is None
    assert result["hardware_amortization_per_encounter"] is None
    assert result["estimated_cost_per_encounter"] is None


def test_explicit_zero_energy_price_is_not_confused_with_missing_cost():
    scenario = json.loads(
        (ROOT / "evaluation/protocols/unit-economics-assumptions-v1.json").read_text(
            encoding="utf-8"
        )
    )
    scenario["inputs"]["electricity_price_per_kwh"]["value"] = 0

    result = estimate(scenario)

    assert result["status"] == "estimated"
    assert result["energy_cost_per_encounter"] == 0
    assert result["estimated_cost_per_encounter"] > 0


def test_invalid_model_availability_is_rejected():
    import pytest

    scenario = json.loads(
        (ROOT / "evaluation/protocols/unit-economics-assumptions-v1.json").read_text(
            encoding="utf-8"
        )
    )
    scenario["inputs"]["model_availability_fraction"]["value"] = 1.2
    with pytest.raises(ValueError, match="availability_must_be_fraction"):
        estimate(scenario)
