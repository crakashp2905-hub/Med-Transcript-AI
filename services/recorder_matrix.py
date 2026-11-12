"""Synthetic browser recorder storage/playback matrix."""


def matrix(*, duration_minutes=30, channels=(1, 2, 4, 8), max_bytes=500_000_000):
    if duration_minutes != 30 or tuple(channels) != (1, 2, 4, 8) or max_bytes <= 0:
        raise ValueError("invalid_recorder_matrix")
    return {
        "duration_minutes": duration_minutes,
        "channels": list(channels),
        "max_bytes": max_bytes,
        "playback_required": True,
        "synthetic_only": True,
    }
