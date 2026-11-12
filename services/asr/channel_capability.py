"""Truthful hardware channel capability detection."""


def detect(*, reported_channels, source="hardware"):
    if not isinstance(reported_channels, int) or reported_channels < 1:
        raise ValueError("invalid_channel_count")
    if source not in ("hardware", "file_metadata", "generated"):
        raise ValueError("invalid_channel_source")
    return {
        "channels": reported_channels,
        "source": source,
        "two_channel_supported": reported_channels >= 2 and source != "generated",
        "hardware_confirmed": source == "hardware",
        "role_assignment": "clinician_confirmation_required",
    }
