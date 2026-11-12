import hashlib
import json
import wave

import pytest

from services.asr.error_review import build_html, build_payload


def test_review_html_binds_exact_audio_reference_alternatives_and_model_digests(
    tmp_path,
):
    audio_root = tmp_path / "dataset"
    audio_root.mkdir()
    audio_path = audio_root / "clip.wav"
    with wave.open(str(audio_path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x01\x00" * 1600)
    audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    manifest_path = audio_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_id": "review-fixture-v1",
                "samples": [
                    {
                        "sample_id": "clip-1",
                        "group_id": "consult-1",
                        "speaker_role": "patient",
                        "audio": "clip.wav",
                        "audio_sha256": audio_hash,
                        "source_start_seconds": 4.0,
                        "source_end_seconds": 4.1,
                        "reference": "No fever",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    report_path = tmp_path / "candidate.json"
    report_path.write_text(
        json.dumps(
            {
                "manifest_sha256": manifest_hash,
                "profile_id": "local-model-a",
                "model_revision": "a" * 40,
                "profile_sha256": "b" * 64,
                "runtime_configuration": {"artifacts": {"model.bin": "c" * 64}},
                "samples": [
                    {
                        "sample_id": "clip-1",
                        "reference": "No fever",
                        "hypothesis": "Fever",
                        "status": "completed",
                        "normalized_edits": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "review.html"
    payload = build_html(manifest_path, [report_path], audio_root, output_path)
    item = payload["review_items"][0]
    assert item["audio_sha256"] == audio_hash
    assert item["reference"] == "No fever"
    assert item["source_start_seconds"] == 4.0
    assert item["source_end_seconds"] == 4.1
    assert item["alternatives"][0]["hypothesis"] == "Fever"
    assert item["alternatives"][0]["model_revision"] == "a" * 40
    assert item["alternatives"][0]["artifact_digests"]["model.bin"] == "c" * 64
    markup = output_path.read_text(encoding="utf-8")
    assert "createElement('audio')" in markup
    assert "Frozen reference" in markup
    assert "Open exact clip" in markup
    assert "model.bin" in markup
    with pytest.raises(FileExistsError):
        build_html(manifest_path, [report_path], audio_root, output_path)


def test_review_builder_rejects_tampered_audio_or_reference(tmp_path):
    audio_root = tmp_path / "dataset"
    audio_root.mkdir()
    audio_path = audio_root / "clip.wav"
    with wave.open(str(audio_path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x00\x00" * 1600)
    audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    manifest_path = audio_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_id": "review-fixture-v1",
                "samples": [
                    {
                        "sample_id": "clip-1",
                        "group_id": "consult-1",
                        "audio": "clip.wav",
                        "audio_sha256": audio_hash,
                        "source_start_seconds": 0,
                        "source_end_seconds": 0.1,
                        "reference": "No fever",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    report_path = tmp_path / "candidate.json"
    report = {
        "manifest_sha256": manifest_hash,
        "profile_id": "local-model-a",
        "model_revision": "a" * 40,
        "profile_sha256": "b" * 64,
        "samples": [
            {
                "sample_id": "clip-1",
                "reference": "Changed reference",
                "hypothesis": "Fever",
                "status": "completed",
                "normalized_edits": 1,
            }
        ],
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="reference_mismatch"):
        build_payload(
            manifest_path,
            [report_path],
            audio_root,
            tmp_path / "review.html",
        )
    report["samples"][0]["reference"] = "No fever"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    audio_path.write_bytes(audio_path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="audio_digest_mismatch"):
        build_payload(
            manifest_path,
            [report_path],
            audio_root,
            tmp_path / "review.html",
        )
