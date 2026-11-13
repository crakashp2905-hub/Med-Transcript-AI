import json
from pathlib import Path

import pytest

from services.experiment_receipts import validate_receipts


RECEIPT = Path("evaluation/reports/experiment-receipts-v1.json")


def test_historical_asr_pilot_has_hypothesis_and_harmful_outcome():
    result = validate_receipts(RECEIPT)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    experiment = receipt["experiments"][0]
    assert result["experiment_count"] == 1
    assert experiment["outcome"] == "harmful_regression"
    assert (
        experiment["result"]["baseline_normalized_wer"]
        < experiment["result"]["candidate_normalized_wer"]
    )
    assert (
        experiment["result"]["candidate_false_insertions"]
        > experiment["result"]["baseline_false_insertions"]
    )


def test_experiment_receipt_requires_hash_bound_evidence(tmp_path):
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt["experiments"][0]["evidence"][0]["sha256"] = "0" * 64
    altered = tmp_path / "receipt.json"
    altered.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence_hash_mismatch"):
        validate_receipts(altered)
