from services.channel_detectors import classify


def test_channel_detectors_flag_cross_talk_swap_empty_fake_stereo_and_drift():
    result = classify(
        channels=2,
        mappings=[
            {"rms": 1, "mapping_matches": False, "signal_hash": "same"},
            {"rms": 0, "mapping_matches": False, "signal_hash": "same"},
        ],
        crosstalk_db=[1, 0],
        duration_match=False,
    )
    assert result["cross_talk_channels"] == [0]
    assert result["channel_swaps"] == [0]
    assert result["empty_channels"] == [1]
    assert result["mono_fake_stereo"] is True and result["desynchronized"] is True
    assert result["requires_review"] is True
