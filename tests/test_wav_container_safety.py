"""Adversarial RIFF chunk layouts fail closed before media publication."""

import struct

import pytest

from services.api.ingest import InvalidAudio, inspect_pcm_wav


def riff(chunks):
    payload = b"WAVE" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(payload)) + payload


def chunk(kind, body):
    return (
        kind + struct.pack("<I", len(body)) + body + (b"\0" if len(body) % 2 else b"")
    )


FMT = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
VALID = [chunk(b"fmt ", FMT), chunk(b"data", b"\0\0")]


@pytest.mark.parametrize(
    "chunks",
    [
        pytest.param(
            [chunk(b"data", b"\0\0"), *VALID[:1], VALID[1]], id="data-before-format"
        ),
        pytest.param([*VALID, chunk(b"fmt ", FMT)], id="duplicate-format"),
        pytest.param(
            [VALID[0], VALID[1], chunk(b"data", b"\0\0")], id="duplicate-audio-payload"
        ),
        pytest.param([chunk(b"fmt ", FMT[:-1]), VALID[1]], id="short-format-body"),
        pytest.param(
            [VALID[0], b"JUNK" + struct.pack("<I", 2**32 - 1)], id="forged-chunk-length"
        ),
    ],
)
def test_malicious_or_inconsistent_riff_chunks_are_rejected(tmp_path, chunks):
    source = tmp_path / "malformed.wav"
    source.write_bytes(riff(chunks))

    with pytest.raises(InvalidAudio):
        inspect_pcm_wav(source)


def test_excessive_riff_chunk_count_is_rejected(tmp_path):
    source = tmp_path / "many-chunks.wav"
    empty_chunk = chunk(b"JUNK", b"")
    source.write_bytes(riff([*([empty_chunk] * 1024), *VALID]))

    with pytest.raises(InvalidAudio, match="invalid_media"):
        inspect_pcm_wav(source)


def test_unknown_odd_sized_chunk_with_valid_padding_is_accepted(tmp_path):
    source = tmp_path / "padded-unknown.wav"
    source.write_bytes(riff([VALID[0], chunk(b"JUNK", b"x"), VALID[1]]))

    assert inspect_pcm_wav(source)["frames"] == 1
