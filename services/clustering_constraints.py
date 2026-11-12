"""Development-only deterministic clustering assumptions."""


def declare(*, expected_speakers, case_scope="development"):
    if case_scope != "development":
        raise ValueError("clustering_assumption_not_for_production")
    if (
        not isinstance(expected_speakers, int)
        or expected_speakers < 1
        or expected_speakers > 16
    ):
        raise ValueError("invalid_expected_speaker_count")
    return {
        "expected_speakers": expected_speakers,
        "case_scope": case_scope,
        "assumption_declared": True,
        "production_acceptance": False,
    }
