import hashlib
import json

import pytest

from services.asr.segmentation_source_map_report import (
    MODES,
    build_source_map_report,
)


def _fixture(tmp_path, monkeypatch, *, wrong_audio=False):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    cases = []
    reference = "hello there"
    ref_sha = hashlib.sha256(reference.encode()).hexdigest()
    for index in range(16):
        cases.append(
            {
                "group_id": f"group-{index:02}",
                "condition": "clean",
                "foreground_id": f"foreground-{index:02}",
                "donor_id": None,
                "audio": f"{index:02}.wav",
                "audio_sha256": f"{index + 1:064x}",
                "reference_turns": [{"reference": reference}],
            }
        )
    manifest = {"cases": cases}
    suite = {
        "manifest_sha256": "a" * 64,
        "jobs": [
            {
                "candidate_id": "faster-whisper-tiny.en",
                "source_profile_sha256": "b" * 64,
            }
        ],
    }
    monkeypatch.setattr(
        "services.asr.segmentation_source_map_report.validate_suite",
        lambda _: (suite_path, suite, manifest_path, manifest),
    )
    paths = []
    for mode in MODES:
        rows = []
        for index, case in enumerate(cases):
            rows.append(
                {
                    "group_id": case["group_id"],
                    "audio_sha256": (
                        "f" * 64
                        if wrong_audio and mode == "pause_aware" and index == 0
                        else case["audio_sha256"]
                    ),
                    "reference_sha256": ref_sha,
                    "failed": False,
                    "window_count": 1,
                    "chunks": [
                        {
                            "window_id": f"{mode}:mix:0",
                            "start_frame": 0,
                            "end_frame_exclusive": 1600,
                            "channel_index": None,
                            "native_segments": [
                                {
                                    "start_ms": 10.0,
                                    "end_ms": 110.0 if index == 0 else 90.0,
                                    "text": "hello",
                                }
                            ],
                        }
                    ],
                }
            )
        report = {
            "schema_version": "asr_segmentation_mode_receipt_v1",
            "complete": True,
            "configuration": {
                "mode": mode,
                "profile_sha256": "b" * 64,
            },
            "bindings": {
                "suite_sha256": hashlib.sha256(b"{}").hexdigest(),
                "manifest_sha256": "a" * 64,
                "source_sha256": {"runner": "c" * 64},
            },
            "cases": rows,
        }
        path = tmp_path / f"{mode}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        paths.append(path)
    return suite_path, paths


def test_source_map_report_preserves_window_ids_and_invalid_timestamps(
    tmp_path, monkeypatch
):
    suite_path, paths = _fixture(tmp_path, monkeypatch)

    report = build_source_map_report(
        paths, tmp_path / "source-map.json", suite_path=suite_path
    )

    assert report["complete"] is True
    assert report["inference_executed"] is False
    assert report["case_count"] == 16
    assert report["native_segment_count"] == 64
    assert report["source_frame_mapping"]["sample_rate"] == 16000
    for mode, result in report["modes"].items():
        assert result["summary"]["native_segments"] == 16
        assert result["summary"]["mapped_segments"] == 15
        assert result["summary"]["invalid_window_timestamps"] == 1
        assert result["summary"]["round_trip_failures"] == 0
        first = result["files"][0]["segments"][0]
        assert first["window_id"] == f"{mode}:mix:0"
        assert first["source_start_frame"] is None
        assert first["source_end_frame_exclusive"] is None
        assert first["source_timestamp_in_window"] is False
        assert first["source_mapping_kind"] == "unavailable_invalid_window_timestamp"
        valid = result["files"][1]["segments"][0]
        assert valid["source_start_frame"] == 160
        assert valid["source_end_frame_exclusive"] == 1440
        assert valid["source_round_trip_valid"] is True


def test_source_map_report_rejects_changed_audio_hash(tmp_path, monkeypatch):
    suite_path, paths = _fixture(tmp_path, monkeypatch, wrong_audio=True)

    with pytest.raises(ValueError, match="source_map_case_source_or_failure_mismatch"):
        build_source_map_report(
            paths, tmp_path / "source-map.json", suite_path=suite_path
        )
