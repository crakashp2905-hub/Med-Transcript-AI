"""Bounded input validation before expensive processing."""


def validate(*, request_bytes, audio_seconds, json_depth, decompressed_bytes, timestamp_seconds, stage,
             max_request=25_000_000, max_audio=3600, max_depth=20, max_decompressed=100_000_000,
             max_timestamp=86_400):
    checks = {
        'request_size': request_bytes <= max_request,
        'audio_duration': audio_seconds <= max_audio,
        'json_depth': json_depth <= max_depth,
        'decompressed_size': decompressed_bytes <= max_decompressed,
        'timestamp_range': abs(timestamp_seconds) <= max_timestamp,
        'stage_present': bool(stage),
    }
    return {'accepted': all(checks.values()), 'checks': checks,
            'rejection_reasons': sorted(key for key, value in checks.items() if not value)}
