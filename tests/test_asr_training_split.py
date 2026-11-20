import pytest

from services.asr.training_split import assign_group_splits, _manifest_rows


def test_training_split_assigns_original_consultation_groups_exclusively():
    assignments = assign_group_splits(
        {"consultation_train_a", "consultation_train_b"},
        {"consultation_dev", "donor_dev"},
        {"day5_consultation05", "day5_consultation06", "day5_consultation07"},
    )
    assert assignments["consultation_train_a"] == "training"
    assert assignments["consultation_dev"] == "development"
    assert assignments["donor_dev"] == "development"
    assert assignments["day5_consultation06"] == "reserved_acceptance"


@pytest.mark.parametrize(
    ("train", "development", "reserved"),
    [
        ({"same"}, {"same"}, set()),
        ({"same"}, set(), {"same"}),
        (set(), {"dev"}, set()),
    ],
)
def test_training_split_rejects_overlapping_or_empty_train_boundaries(
    train, development, reserved
):
    with pytest.raises(
        ValueError, match="training_development_acceptance_groups_must_be_disjoint"
    ):
        assign_group_splits(train, development, reserved)


def test_distracted_case_keeps_foreground_and_donor_in_same_split():
    rows = _manifest_rows(
        "fixture",
        {
            "cases": [
                {
                    "group_id": "consultation_dev__distracted",
                    "foreground_id": "consultation_dev",
                    "donor_id": "donor_dev",
                    "audio": "case.wav",
                    "audio_sha256": "a" * 64,
                    "condition": "distracted",
                    "reference_turns": [
                        {"reference": "example", "uncertain_reference": False}
                    ],
                }
            ]
        },
    )
    assert rows[0]["consultation_group_id"] == "consultation_dev"
    assert rows[0]["contributing_group_ids"] == ["consultation_dev", "donor_dev"]
