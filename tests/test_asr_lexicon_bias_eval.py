from services.asr.lexicon_bias_eval import _select_pairs


def test_pair_selection_uses_clean_positive_and_nearest_non_target_reference():
    manifest = {
        "cases": [
            {
                "group_id": "case-clean",
                "foreground_id": "group-a",
                "condition": "clean",
                "reference_turns": [
                    {
                        "reference": "No medication mentioned.",
                        "uncertain_reference": False,
                    },
                    {
                        "reference": "Take paracetamol today.",
                        "uncertain_reference": False,
                    },
                    {
                        "reference": "Take paracetamol tomorrow.",
                        "uncertain_reference": False,
                    },
                ],
            },
            {
                "group_id": "case-noisy",
                "foreground_id": "group-b",
                "condition": "distracted",
                "reference_turns": [
                    {
                        "reference": "Take paracetamol today.",
                        "uncertain_reference": False,
                    }
                ],
            },
        ]
    }
    pairs = _select_pairs(manifest, "paracetamol")
    assert [row[0] for row in pairs] == ["positive", "negative"]
    assert pairs[0][2] == 1
    assert pairs[1][2] == 0
