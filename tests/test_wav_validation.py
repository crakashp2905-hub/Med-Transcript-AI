import random
import struct
import wave
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from services.api.ingest import (
    InvalidAudio,
    MAX_UPLOAD_BYTES,
    inspect_pcm_wav,
    run_once,
)
from services.api.storage import Store


def make_wav(path, channels=1, sample_rate=16000, sample_width=2, samples=160):
    with wave.open(str(path), "wb") as output:
        output.setparams(
            (channels, sample_width, sample_rate, 0, "NONE", "not compressed")
        )
        output.writeframes(b"\0" * samples * channels * sample_width)
    return bytearray(path.read_bytes())


@pytest.mark.parametrize(
    ("offset", "value", "width", "error"),
    [
        (20, 3, 2, "unsupported_media"),  # IEEE float instead of PCM
        (22, 0, 2, "unsupported_media"),
        (22, 9, 2, "unsupported_media"),
        (24, 7999, 4, "unsupported_media"),
        (24, 48001, 4, "unsupported_media"),
        (34, 8, 2, "unsupported_media"),
        (32, 4, 2, "invalid_media"),  # channel count no longer matches block alignment
        (28, 1, 4, "invalid_media"),  # byte rate no longer matches sample rate
        (40, 321, 4, "invalid_media"),  # data chunk splits a PCM frame
    ],
)
def test_rejects_wav_profile_and_frame_inconsistencies(
    tmp_path, offset, value, width, error
):
    source = tmp_path / "mutated.wav"
    body = make_wav(source)
    body[offset : offset + width] = value.to_bytes(width, "little")
    if offset == 40:
        body.extend(b"\0\0")
        body[4:8] = (len(body) - 8).to_bytes(4, "little")
    source.write_bytes(body)
    with pytest.raises(InvalidAudio, match=error):
        inspect_pcm_wav(source)


def test_rejects_truncated_and_oversized_wav_without_reading_payload(tmp_path):
    source = tmp_path / "large.wav"
    make_wav(source)
    with source.open("r+b") as output:
        output.truncate(MAX_UPLOAD_BYTES + 1)
    with pytest.raises(InvalidAudio, match="invalid_media"):
        inspect_pcm_wav(source)

    source.write_bytes(b"RIFF\x20\x00\x00\x00WAVEfmt ")
    with pytest.raises(InvalidAudio, match="invalid_media"):
        inspect_pcm_wav(source)


def test_deterministic_malformed_header_fuzz_fails_safely(tmp_path):
    rng = random.Random(2401)
    source = tmp_path / "fuzzed.wav"
    for _ in range(100):
        body = bytearray(128)
        body[:4] = b"RIFF"
        body[4:8] = struct.pack("<I", 120)
        body[8:12] = b"WAVE"
        body[12:] = rng.randbytes(116)
        source.write_bytes(body)
        with pytest.raises(InvalidAudio):
            inspect_pcm_wav(source)


def test_unsupported_wav_encoding_fails_job_without_publishing_normalized_audio(
    tmp_path,
):
    database = tmp_path / "pipeline.sqlite3"
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    store = Store(str(database))
    upload_id, encounter_id, job_id, authorization_id = map(
        str, (uuid4(), uuid4(), uuid4(), uuid4())
    )
    tenant_id = str(uuid4())
    source = asset_root / f"{upload_id}.wav"
    body = make_wav(source)
    body[20:22] = (3).to_bytes(2, "little")  # IEEE float WAV
    source.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    now = datetime.now(timezone.utc)
    with store.transaction() as connection:
        connection.execute(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
            (encounter_id, tenant_id, str(uuid4()), "{}", now.isoformat()),
        )
        connection.execute(
            "INSERT INTO authorizations(id,encounter,body,created_at) VALUES(?,?,?,?)",
            (
                authorization_id,
                encounter_id,
                json.dumps(
                    {
                        "scopes": ["recording", "local_processing"],
                        "expires_at": (now + timedelta(hours=1)).isoformat(),
                    }
                ),
                now.isoformat(),
            ),
        )
        connection.execute(
            """INSERT INTO uploads
            (id,encounter,expected_bytes,expected_sha256,status,created_at,expires_at,media_type)
            VALUES(?,?,?,?,?,?,?,?)""",
            (
                upload_id,
                encounter_id,
                len(body),
                digest,
                "complete",
                now.isoformat(),
                (now + timedelta(hours=1)).isoformat(),
                "audio/wav",
            ),
        )
        connection.execute(
            """INSERT INTO jobs
            (id,upload,encounter,status,created_at,updated_at,stage)
            VALUES(?,?,?,'queued',?,?,'audio_ingest')""",
            (job_id, upload_id, encounter_id, now.isoformat(), now.isoformat()),
        )

    assert run_once(str(database), str(asset_root))["status"] == "failed"
    with store.transaction() as connection:
        job = connection.execute(
            "SELECT error_code,result FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
    assert job["error_code"] == "unsupported_media"
    assert job["result"] is None
    assert not list(asset_root.glob("*.normalized.wav"))
