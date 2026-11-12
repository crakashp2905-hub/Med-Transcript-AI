from services.channel_scorecard import compare


def test_channel_scorecard_does_not_equate_generated_inputs_with_hardware():
    result = compare(
        {
            "single": {"channels": 1, "source": "hardware"},
            "two": {"channels": 2, "source": "generated"},
            "multi": {"channels": 4, "source": "hardware"},
        }
    )
    assert result["configurations"][1]["hardware_equivalence"] is False
    assert result["hardware_equivalence_claim"] is False
