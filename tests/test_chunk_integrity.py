from services.chunk_integrity import validate_chunk


def test_chunk_integrity_rejects_missing_offset_digest_and_size_faults():
    assert (
        validate_chunk(
            payload=None,
            expected_offset=0,
            actual_offset=0,
            expected_digest="a",
            actual_digest="a",
        )["reason"]
        == "missing_chunk"
    )
    assert (
        validate_chunk(
            payload=b"x",
            expected_offset=0,
            actual_offset=1,
            expected_digest="a",
            actual_digest="a",
        )["reason"]
        == "offset_mismatch"
    )
    assert (
        validate_chunk(
            payload=b"x",
            expected_offset=0,
            actual_offset=0,
            expected_digest="a",
            actual_digest="b",
        )["reason"]
        == "digest_mismatch"
    )
    assert (
        validate_chunk(
            payload=b"xx",
            expected_offset=0,
            actual_offset=0,
            expected_digest="a",
            actual_digest="a",
            max_bytes=1,
        )["reason"]
        == "oversized_chunk"
    )


def test_chunk_integrity_accepts_ordered_valid_chunk():
    assert (
        validate_chunk(
            payload=b"x",
            expected_offset=3,
            actual_offset=3,
            expected_digest="a",
            actual_digest="a",
        )["accepted"]
        is True
    )
