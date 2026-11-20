import hashlib
import json
import wave
from array import array

import pytest

from services.asr.segmentation_boundary_report import (
    MODES,
    build_boundary_report,
)


def _audio(path):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(array("h", [1000] * 3200).tobytes())
    return path


def _fixture(tmp_path, monkeypatch, *, invalid_window=False):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    audio_root = tmp_path / "audio"
    audio_root.mkdir()
    cases, hashes = [], {}
    for index in range(16):
        audio_path = _audio(audio_root / f"case-{index:02}.wav")
        audio_sha256 = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        reference = "brief answer doctor asks patient replies uncertain response"
        reference_sha256 = hashlib.sha256(reference.encode()).hexdigest()
        case = {
            "group_id": f"group-{index:02}",
            "audio": audio_path.name,
            "audio_sha256": audio_sha256,
            "condition": "clean",
            "foreground_id": f"foreground-{index:02}",
            "donor_id": None,
            "reference_turns": [
                {
                    "start_ms": 5,
                    "end_ms": 30,
                    "role": "patient",
                    "reference": "brief answer",
                },
                {
                    "start_ms": 80,
                    "end_ms": 140,
                    "role": "doctor",
                    "reference": "doctor asks",
                },
                {
                    "start_ms": 130,
                    "end_ms": 180,
                    "role": "patient",
                    "reference": "patient replies",
                },
                {
                    "start_ms": 185,
                    "end_ms": 195,
                    "role": None,
                    "reference": "uncertain response",
                },
            ],
        }
        cases.append(case)
        hashes[case["group_id"]] = (audio_sha256, reference_sha256)
    manifest = {"cases": cases}
    suite = {
        "manifest_sha256": "a" * 64,
        "audio_root": str(audio_root),
        "jobs": [
            {
                "candidate_id": "faster-whisper-tiny.en",
                "source_profile_sha256": "b" * 64,
            }
        ],
    }
    monkeypatch.setattr(
        "services.asr.segmentation_boundary_report.validate_suite",
        lambda _: (suite_path, suite, manifest_path, manifest),
    )
    receipt_paths = []
    source_sha = {"runner": "c" * 64}
    for mode in MODES:
        rows = []
        for index, case in enumerate(cases):
            audio_sha256, reference_sha256 = hashes[case["group_id"]]
            windows = (
                [
                    {
                        "window_id": "fixed:0",
                        "start_frame": 500,
                        "end_frame_exclusive": 2200,
                    },
                    {
                        "window_id": "fixed:1",
                        "start_frame": 1800,
                        "end_frame_exclusive": 3200,
                    },
                ]
                if mode == "fixed_window"
                else [
                    {
                        "window_id": f"{mode}:0",
                        "start_frame": 0,
                        "end_frame_exclusive": (
                            4000
                            if invalid_window and index == 0 and mode == "pause_aware"
                            else 3200
                        ),
                    }
                ]
            )
            rows.append(
                {
                    "group_id": case["group_id"],
                    "audio_sha256": audio_sha256,
                    "reference_sha256": reference_sha256,
                    "window_count": len(windows),
                    "chunks": windows,
                }
            )
        report = {
            "schema_version": "asr_segmentation_mode_receipt_v1",
            "complete": True,
            "source_commit": "commit-1",
            "configuration": {
                "mode": mode,
                "profile_sha256": "b" * 64,
            },
            "bindings": {
                "suite_sha256": hashlib.sha256(b"{}").hexdigest(),
                "manifest_sha256": "a" * 64,
                "source_sha256": source_sha,
            },
            "cases": rows,
        }
        receipt = tmp_path / f"{mode}.json"
        receipt.write_text(json.dumps(report), encoding="utf-8")
        receipt_paths.append(receipt)
    return suite_path, receipt_paths


def test_boundary_report_measures_turn_edges_roles_and_short_omissions(
    tmp_path, monkeypatch
):
    suite_path, receipts = _fixture(tmp_path, monkeypatch)

    report = build_boundary_report(
        receipts, tmp_path / "boundary.json", suite_path=suite_path
    )

    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["case_count"] == 16
    assert report["turn_time_mapping"]["short_turn_threshold_frames"] == 1600
    assert (
        report["boundary_metric_scope"]
        == "reference_turn_interval_intersections_not_word_alignment"
    )
    fixed = report["modes"]["fixed_window"]["files"][0]
    assert fixed["summary"]["omitted_short_turns"] == 1
    assert fixed["summary"]["clipped_turns"] == 2
    assert fixed["summary"]["windows_joining_known_roles"] == 2
    assert fixed["summary"]["windows_with_unknown_role_turns"] == 1
    pause = report["modes"]["pause_aware"]["files"][0]
    assert pause["summary"]["omitted_short_turns"] == 0
    assert pause["summary"]["clipped_turns"] == 0


def test_boundary_report_rejects_windows_outside_source_audio(tmp_path, monkeypatch):
    suite_path, receipts = _fixture(tmp_path, monkeypatch, invalid_window=True)

    with pytest.raises(ValueError, match="segmentation_window_outside_source_audio"):
        build_boundary_report(
            receipts, tmp_path / "boundary.json", suite_path=suite_path
        )
