"""Pin the current full-consultation fixed-window baseline before optimization."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT / "evaluation/reports/detailed-campaign-execution-receipt-2026-10-29.json"
)
RANKING = ROOT / "evaluation/reports/detailed-ranking-final-2026-10-29.json"
SUITE = ROOT / "evaluation/detailed-suite-v2.json"
EXPECTED_CANDIDATE = "omi-med-stt-v1-native-empty"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixed_window_winner_and_paired_segmentation_arms_are_source_bound():
    receipt, ranking, suite = map(read_json, (RECEIPT, RANKING, SUITE))
    assert receipt["baseline_comparison_complete"] is True
    assert ranking["complete"] is True
    assert suite["maximum_normalized_wer"] == 0.05
    assert ranking["ranked"][0]["candidate_id"] == EXPECTED_CANDIDATE

    rows = {
        row["mode"]: row
        for row in receipt["completed_conditions"]
        if row["candidate"] == EXPECTED_CANDIDATE
    }
    assert set(rows) == {"fixed", "overlap", "speech_aware"}
    observed = {}
    for mode, row in rows.items():
        report_path = ROOT / row["report"]
        assert hashlib.sha256(report_path.read_bytes()).hexdigest() == row["sha256"]
        report = read_json(report_path)
        assert report["complete"] is True
        assert report["mode"] == mode
        assert report["manifest_sha256"] == receipt["manifest_sha256"]
        assert report["suite_sha256"] == receipt["suite_sha256"]
        for condition in ("clean", "distracted"):
            result = report["conditions"][condition]
            assert result["samples"] == 8
            assert result["failed_samples"] == 0
            assert result["reference_words"] == 13683
            assert result["normalized_wer"] == row[condition]["normalized_wer"]
            assert result["normalized_wer"] > suite["maximum_normalized_wer"]
            observed.setdefault(condition, {})[mode] = result["normalized_wer"]

    for condition in ("clean", "distracted"):
        fixed = observed[condition]["fixed"]
        assert observed[condition]["overlap"] > fixed
        assert observed[condition]["speech_aware"] > fixed
