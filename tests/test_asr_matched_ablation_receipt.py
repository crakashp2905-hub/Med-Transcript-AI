import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evaluation/runs/meddistract-detailed-v7/matched-ablation-v3.json"
REPORT_SHA256 = "12c074f9029f68f4882aa455b320e05e9c182b0e1928185275942a26e6a702c7"


def _reference(case):
    return " ".join(
        re.sub(r"<[^>]+>", "", turn["reference"]) for turn in case["reference_turns"]
    )


def test_matched_ablation_receipt_recomputes_all_arms_and_failure_deletions():
    assert hashlib.sha256(REPORT_PATH.read_bytes()).hexdigest() == REPORT_SHA256
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    suite = json.loads(
        (ROOT / "evaluation/detailed-suite-v7.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((ROOT / suite["manifest"]).read_text(encoding="utf-8"))
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["automatic_promotion"] is False
    assert report["bindings"]["manifest_sha256"] == suite["manifest_sha256"]
    assert (
        report["bindings"]["runner_sha256"]
        == report["bindings"]["source_sha256"][
            str((ROOT / "services/asr/matched_ablation_runner.py").resolve()).replace(
                "\\", "/"
            )
        ]
    )
    assert report["comparison"]["sample_count"] == 16
    assert set(report["arm_outputs"]) == set(report["comparison"]["arms"])
    expected_cases = {case["group_id"]: case for case in manifest["cases"]}
    for arm_id, arm in report["arm_outputs"].items():
        rows = arm["cases"]
        assert len(rows) == len(expected_cases)
        assert {row["group_id"] for row in rows} == set(expected_cases)
        for row in rows:
            case = expected_cases[row["group_id"]]
            assert row["audio_sha256"] == case["audio_sha256"]
            assert row["condition"] == case["condition"]
            assert row["foreground_id"] == case["foreground_id"]
            assert row["donor_id"] == case.get("donor_id")
            expected_reference_sha = hashlib.sha256(
                _reference(case).encode("utf-8")
            ).hexdigest()
            assert row["reference_sha256"] == expected_reference_sha
            if row["failed"]:
                assert row["hypothesis"] == ""
        summary = report["comparison"]["arms"][arm_id]
        assert summary["sample_count"] == len(rows)
        assert summary["failed_samples"] == sum(row["failed"] for row in rows)
        assert summary["normalized_edits"] == sum(
            row["normalized_edits"] for row in rows
        )
        assert summary["reference_words"] == sum(row["reference_words"] for row in rows)
        assert (
            summary["normalized_wer"]
            == summary["normalized_edits"] / summary["reference_words"]
        )
    assert report["comparison"]["arms"]["vad_only"]["failed_samples"] == 2
    assert report["comparison"]["arms"]["repair_only"]["failed_samples"] == 1
    assert all(
        arm["normalized_wer"] > 0.05 for arm in report["comparison"]["arms"].values()
    )


def test_matched_terminology_arm_records_positive_and_negative_term_outcomes():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    suite = json.loads(
        (ROOT / "evaluation/detailed-suite-v7.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((ROOT / suite["manifest"]).read_text(encoding="utf-8"))
    lexicon = json.loads(
        (ROOT / "evaluation/lexicons/clinical-english-v1-e01.json").read_text(
            encoding="utf-8"
        )
    )
    term = lexicon["entries"][0]["term"]
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.I)
    references = {case["group_id"]: _reference(case) for case in manifest["cases"]}
    positive_ids = {
        group_id
        for group_id, reference in references.items()
        if pattern.search(reference)
    }
    negative_ids = set(references) - positive_ids
    rows = {
        arm_id: {row["group_id"]: row for row in arm["cases"]}
        for arm_id, arm in report["arm_outputs"].items()
    }

    def counts(arm_id):
        arm_rows = rows[arm_id]
        return {
            "positive_recall": sum(
                bool(pattern.search(arm_rows[group_id]["hypothesis"]))
                for group_id in positive_ids
            ),
            "negative_false_insertions": sum(
                bool(pattern.search(arm_rows[group_id]["hypothesis"]))
                for group_id in negative_ids
            ),
        }

    assert len(positive_ids) == 12
    assert len(negative_ids) == 4
    assert counts("fixed_baseline") == {
        "positive_recall": 6,
        "negative_false_insertions": 0,
    }
    assert counts("terminology_only") == {
        "positive_recall": 12,
        "negative_false_insertions": 0,
    }
    assert (
        report["comparison"]["arms"]["terminology_only"]["normalized_wer"]
        > report["comparison"]["arms"]["fixed_baseline"]["normalized_wer"]
    )
