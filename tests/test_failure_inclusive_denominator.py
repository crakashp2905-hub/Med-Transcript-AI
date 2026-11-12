import pytest

from services.benchmark_integrity import replay
from services.detailed_benchmark import fast_score


def test_replay_requires_all_predeclared_cases_and_keeps_failed_cases():
    manifest = {
        "cases": [
            {
                "group_id": "one",
                "audio_sha256": "a",
                "reference_turns": [{"reference": "one two"}],
            }
        ]
    }
    report = {
        "complete": True,
        "cases": [
            {
                "id": "one",
                "input_sha256": "a",
                "reference": "one two",
                "hypothesis": "not empty",
                "failed": True,
                "input_coverage_complete": True,
                **fast_score("one two", "not empty"),
            }
        ],
    }
    with pytest.raises(ValueError, match="failure_denominator"):
        replay(report, manifest)
