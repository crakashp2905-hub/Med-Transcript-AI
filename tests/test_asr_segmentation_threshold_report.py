import hashlib
import json

import pytest

from services.asr.segmentation_candidate_runner import (
    ACTIVITY_PROFILE,
    MODE_CONFIGS,
    VAD_THRESHOLD_VARIANTS,
    _summarize,
    fast_score,
)
from services.asr.segmentation_threshold_report import build_threshold_matrix


def _case(index):
    return {
        "group_id": f"case-{index:02}",
        "condition": "clean",
        "foreground_id": f"foreground-{index:02}",
        "donor_id": None,
        "audio_sha256": f"{index + 1:064x}",
        "reference_turns": [{"reference": "hello there"}],
    }


def _receipts(tmp_path, monkeypatch, changed_input=False):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest = {"cases": [_case(index) for index in range(16)]}
    suite = {
        "manifest_sha256": "a" * 64,
        "maximum_normalized_wer": 0.05,
        "jobs": [
            {
                "candidate_id": "faster-whisper-tiny.en",
                "source_profile_sha256": "b" * 64,
            }
        ],
    }
    monkeypatch.setattr(
        "services.asr.segmentation_threshold_report.validate_suite",
        lambda _: (suite_path, suite, manifest_path, manifest),
    )
    source_sha256 = {"runner.py": "c" * 64}
    receipt_paths = []
    arm_configs = {"baseline": MODE_CONFIGS["vad_cut_merge"]}
    arm_configs.update(VAD_THRESHOLD_VARIANTS)
    for arm_id, parameters in arm_configs.items():
        variant = None if arm_id == "baseline" else arm_id
        cases = []
        for index, source in enumerate(manifest["cases"]):
            reference = "hello there"
            hypothesis = "hello there"
            if arm_id == "padding_600ms" and index == 0:
                hypothesis = "hello"
            reference_sha = hashlib.sha256(reference.encode()).hexdigest()
            cases.append(
                {
                    "group_id": source["group_id"],
                    "condition": source["condition"],
                    "foreground_id": source["foreground_id"],
                    "donor_id": source["donor_id"],
                    "audio_sha256": (
                        "f" * 64
                        if changed_input and arm_id == "padding_600ms" and index == 0
                        else source["audio_sha256"]
                    ),
                    "reference_sha256": reference_sha,
                    "reference": reference,
                    "hypothesis": hypothesis,
                    "failed": False,
                    "reference_words": 2,
                    "normalized_edits": fast_score(reference, hypothesis)[
                        "normalized_edits"
                    ],
                    "wall_seconds": 1.0,
                }
            )
        config = {
            "mode": "vad_cut_merge",
            "mode_parameters": parameters,
            "activity_profile": ACTIVITY_PROFILE,
            "activity_profile_sha256": hashlib.sha256(
                json.dumps(
                    ACTIVITY_PROFILE, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            "profile_sha256": "b" * 64,
        }
        if variant:
            config["variant_id"] = variant
        report = {
            "schema_version": "asr_segmentation_mode_receipt_v1",
            "complete": True,
            "source_commit": "commit-a",
            "configuration": config,
            "bindings": {
                "suite_sha256": hashlib.sha256(b"{}").hexdigest(),
                "manifest_sha256": "a" * 64,
                "profile_sha256": "b" * 64,
                "source_sha256": source_sha256,
            },
            "summary": _summarize(cases),
            "resource_measurement": {
                "status": "measured",
                "peak_resident_bytes": 123,
            },
            "cases": cases,
        }
        path = tmp_path / f"{arm_id}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        receipt_paths.append(path)
    return suite_path, receipt_paths


def test_threshold_report_reconciles_single_factor_matched_arms(tmp_path, monkeypatch):
    suite_path, receipts = _receipts(tmp_path, monkeypatch)

    report = build_threshold_matrix(
        receipts, tmp_path / "threshold-matrix.json", suite_path=suite_path
    )

    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["case_count"] == 16
    assert report["reference_words"] == 32
    assert report["wer_admission_maximum"] == 0.05
    assert set(report["arms"]) == {"baseline", *VAD_THRESHOLD_VARIANTS}
    assert report["arms"]["padding_600ms"]["summary"]["normalized_edits"] > 0


def test_threshold_report_rejects_input_hash_mismatch(tmp_path, monkeypatch):
    suite_path, receipts = _receipts(tmp_path, monkeypatch, changed_input=True)

    with pytest.raises(ValueError, match="vad_threshold_case_evidence_mismatch"):
        build_threshold_matrix(
            receipts, tmp_path / "threshold-matrix.json", suite_path=suite_path
        )
