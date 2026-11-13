import copy
import json
from pathlib import Path

import pytest

from services.beccsv_ablations import validate_matrix


def _matrix():
    return json.loads(
        Path("evaluation/contracts/beccsv-ablation-matrix-v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_beccsv_ablation_matrix_has_full_and_single_feature_removal_arms():
    result = validate_matrix(_matrix())
    assert result == {
        "variant_count": 7,
        "single_feature_ablations": 6,
        "executed": False,
        "clinical_release_authorized": False,
    }


@pytest.mark.parametrize(
    "mutation",
    ["remove_two_features", "change_full_policy", "claim_executed", "claim_release"],
)
def test_invalid_beccsv_ablation_matrix_fails_closed(mutation):
    matrix = copy.deepcopy(_matrix())
    if mutation == "remove_two_features":
        matrix["variants"]["no_relation_edges"]["temporal_edges"] = False
    elif mutation == "change_full_policy":
        matrix["variants"]["full_beccsv"]["local_verifier"] = False
    elif mutation == "claim_executed":
        matrix["status"] = "executed"
    else:
        matrix["clinical_release_authorized"] = True

    with pytest.raises(ValueError):
        validate_matrix(matrix)
