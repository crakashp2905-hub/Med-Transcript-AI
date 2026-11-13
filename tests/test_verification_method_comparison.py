import hashlib
import json

import pytest

from services.verification_method_comparison import compare


def test_comparison_keeps_graph_structural_and_reuses_frozen_model(tmp_path):
    challenge = {
        "scope": "developer_authored_not_gold",
        "cases": [
            {
                "id": "dose_change",
                "category": "dose",
                "source": "Take warfarin 2 mg daily.",
                "claim": "Take warfarin 20 mg daily.",
                "unsafe": True,
            },
            {
                "id": "dose_safe_control",
                "category": "dose",
                "source": "Take warfarin 2 mg daily.",
                "claim": "Take warfarin 2 mg daily.",
                "unsafe": False,
            },
        ],
    }
    challenge_path = tmp_path / "challenge.json"
    challenge_path.write_text(json.dumps(challenge), encoding="utf-8")
    frozen_path = tmp_path / "frozen.json"
    frozen_path.write_text(
        json.dumps(
            {
                "challenge_sha256": hashlib.sha256(
                    challenge_path.read_bytes()
                ).hexdigest(),
                "cases": [
                    {
                        "id": "dose_change",
                        "model_unsafe": None,
                        "combined_unsafe": True,
                        "model_failure": "clinical_model_timeout",
                    },
                    {
                        "id": "dose_safe_control",
                        "model_unsafe": True,
                        "combined_unsafe": True,
                    },
                ],
                "summary": {
                    "model": {"missing_verdicts": 1},
                    "combined_review_policy": {"attempted": 1},
                },
            }
        ),
        encoding="utf-8",
    )

    report = compare(
        challenge_path,
        frozen_path,
        tmp_path / "report.json",
        source_commit="a" * 40,
    )

    row = report["cases"][0]
    assert row["rules_unsafe"] is True
    assert row["model_unsafe"] is None
    assert row["combined_unsafe"] is True
    assert row["graph_provenance_valid"] is True
    assert row["graph_semantic_verdict"] is None
    assert report["graph_summary"]["clinical_verdicts"] == 0
    assert report["summary"]["deterministic_rules"]["critical_misses"] == 0
    assert report["summary"]["frozen_local_model"]["missing_verdicts"] == 1
    assert report["summary"]["deterministic_rules"]["false_block_rate"] == 0
    assert report["summary"]["frozen_local_model"]["false_block_rate"] == 1
    assert (
        report["summary"]["frozen_combined_review_policy"]["blocks_all_cases"] is True
    )
    failure = report["summary"]["per_category"]["dose"]["failure_dimensions"]
    assert failure["model_timeouts"] == 1
    assert failure["model_abstentions"] == 1
    assert failure["structurally_unsupported_sources"] == 0
    assert failure["structurally_unsupported_source_rate"] == 0
    assert report["model_results_reused_without_inference"] is True


def test_comparison_rejects_frozen_results_for_different_challenge(tmp_path):
    challenge_path = tmp_path / "challenge.json"
    challenge_path.write_text(
        json.dumps(
            {
                "scope": "dev",
                "cases": [
                    {
                        "id": "case",
                        "source": "x",
                        "claim": "y",
                        "unsafe": True,
                        "category": "other",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    frozen_path = tmp_path / "frozen.json"
    frozen_path.write_text(
        json.dumps({"challenge_sha256": "0" * 64, "cases": []}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="frozen_results_challenge_mismatch"):
        compare(
            challenge_path,
            frozen_path,
            tmp_path / "report.json",
            source_commit="a" * 40,
        )
