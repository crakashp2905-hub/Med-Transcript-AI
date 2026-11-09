"""Safe media-format policy independent of optional local codec availability."""

SUPPORTED = {'wav', 'mp3', 'm4a', 'webm', 'ogg'}


def inspect_format(extension, *, codec_available):
    normalized = extension.lower().lstrip('.')
    if normalized not in SUPPORTED:
        return {'supported': False, 'reason': 'unsupported_codec', 'format': normalized}
    if not codec_available:
        return {'supported': False, 'reason': 'codec_unavailable', 'format': normalized}
    return {'supported': True, 'reason': None, 'format': normalized}
