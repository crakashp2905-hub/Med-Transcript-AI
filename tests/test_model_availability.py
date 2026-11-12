from pathlib import Path
import hashlib
import pytest
from services.asr.profiles import ASRProfile, REQUIRED_FILES
from services.asr.adapter import FasterWhisperAdapter, ASRFailure
from services.asr.worker import run_once
from tests.test_transcription import enqueue
from tests.test_foundation import headers


def test_missing_model_is_unavailable_without_loading_or_downloading(
    tmp_path, monkeypatch
):
    model = tmp_path / "model"
    model.mkdir()
    for name in REQUIRED_FILES:
        (model / name).write_bytes(b"fixture")
    profile = ASRProfile(
        profile_id="availability-test",
        model_dir=str(model),
        source="synthetic",
        revision="a" * 40,
        license_id="test-only",
        artifacts={
            name: hashlib.sha256(b"fixture").hexdigest() for name in REQUIRED_FILES
        },
    )
    assert profile.availability()["status"] == "available_not_admitted"
    (model / "model.bin").unlink()
    result = profile.availability()
    assert result["status"] == "unavailable" and not result["automatic_download"]

    def forbidden(*args, **kwargs):
        raise AssertionError("No model load is allowed when artifacts are missing")

    monkeypatch.setattr("services.asr.adapter.loaded_model", forbidden)
    with pytest.raises(ASRFailure) as error:
        FasterWhisperAdapter(profile).transcribe(
            Path("unused-audio.wav"),
            {"channels": 1, "sample_rate": 16000},
            lambda: None,
        )
    assert error.value.code == "model_unavailable"
    (model / "model.bin").write_bytes(b"tampered")
    assert profile.availability()["status"] == "integrity_failed"


def test_network_model_directory_cannot_trigger_native_filesystem_access():
    with pytest.raises(ValueError):
        ASRProfile(
            profile_id="network-test",
            model_dir=r"\\server\share\weights",
            source="synthetic",
            revision="a" * 40,
            license_id="test-only",
            artifacts={name: "a" * 64 for name in REQUIRED_FILES},
        )


def test_worker_missing_model_preserves_audio_and_does_not_publish_transcript(
    environment,
):
    env = environment
    queued = enqueue(env)
    (Path(env.profile.model_dir) / "model.bin").unlink()

    def forbidden(profile):
        raise AssertionError("Unavailable model must not be instantiated")

    result = run_once(env.path, env.assets, adapter_factory=forbidden)
    assert result["status"] == "failed"
    job = env.client.get(queued.job["status_url"], headers=headers()).json()
    assert job["error_code"] == "model_unavailable"
    workspace = env.client.get(
        f"/v1/encounters/{queued.resource}/workspace", headers=headers()
    ).json()
    assert workspace["transcript"] is None and workspace["note"] is None
    assert (
        env.client.get(
            f"/v1/encounters/{queued.resource}/audio/{queued.upload['id']}",
            headers=headers(),
        ).status_code
        == 200
    )
