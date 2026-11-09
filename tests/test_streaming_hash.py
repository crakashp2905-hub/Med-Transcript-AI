import hashlib

from services.api.ingest import file_sha256


def test_audio_hash_streams_bounded_chunks(tmp_path):
    path = tmp_path / 'long-synthetic.bin'
    path.write_bytes((b'0123456789abcdef' * 200000))
    assert file_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()
