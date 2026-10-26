import io
import wave
from pathlib import Path

import pytest

from services.api.ingest import inspect_pcm_wav, run_once
from services.media_decoder import normalize
from tests.test_foundation import setup, queue_upload, headers


def stereo_wav():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setparams((2,2,48000,0,"NONE","not compressed"))
        target.writeframes(b"\1\0\1\0"*4800)
    return buffer.getvalue()


def test_separate_decoder_normalizes_stereo_48k(tmp_path):
    pytest.importorskip("av")
    source, target = tmp_path/"source.wav", tmp_path/"normalized.wav"
    source.write_bytes(stereo_wav())
    result = normalize(source, target, "audio/wav")
    assert result["error_code"] is None, result
    metadata = inspect_pcm_wav(target)
    assert metadata["channels"] == 2 and metadata["sample_rate"] == 16000
    assert metadata["duration_ms"] == 100


def test_ingest_publishes_normalized_asset_after_authorization_check(setup):
    pytest.importorskip("av")
    client, db, _ = setup
    eid, upload, _, queued = queue_upload(client, stereo_wav())
    root = Path(db).parent / "assets"
    assert run_once(db, str(root))["status"] == "succeeded"
    result = client.get(queued["status_url"], headers=headers()).json()["result"]
    assert result["asr_sample_rate"] == 16000
    assert (root / f"{upload['id']}.normalized.wav").is_file()
    assert not list(root.glob("*.*.normalized.wav"))


def test_declared_type_mismatch_is_rejected(tmp_path):
    pytest.importorskip("av")
    source, target = tmp_path/"source.wav", tmp_path/"normalized.wav"
    source.write_bytes(stereo_wav())
    assert normalize(source, target, "audio/mpeg")["error_code"] == "media_type_mismatch"
