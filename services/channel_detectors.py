"""Deterministic channel anomaly classification."""


def classify(*, channels, mappings, crosstalk_db, duration_match):
    if channels < 1 or len(mappings) != channels or len(crosstalk_db) != channels:
        raise ValueError("channel_observations_incomplete")
    empty = [i for i, row in enumerate(mappings) if row.get("rms", 0) <= 0]
    swaps = [
        i
        for i, row in enumerate(mappings)
        if row.get("mapping_matches") is False and i not in empty
    ]
    cross_talk = [i for i, value in enumerate(crosstalk_db) if value > 0]
    return {
        "cross_talk_channels": cross_talk,
        "channel_swaps": swaps,
        "empty_channels": empty,
        "mono_fake_stereo": channels > 1
        and len({row.get("signal_hash") for row in mappings}) == 1,
        "desynchronized": not duration_match,
        "requires_review": bool(cross_talk or swaps or empty or not duration_match),
    }
