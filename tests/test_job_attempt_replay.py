import copy

import pytest

from services.api.job_attempt_replay import build_attempt_replay


ATTEMPTS = [
    {
        "attempt": 1,
        "status": "failed",
        "error_code": "asr_failed",
        "finished_at": "2026-11-14T10:00:00+00:00",
    },
    {
        "attempt": 2,
        "status": "succeeded",
        "error_code": None,
        "finished_at": "2026-11-14T10:00:05+00:00",
    },
]
RETRIES = [
    {
        "id": "retry-event-1",
        "action": "transcription_retry_queued",
        "time": "2026-11-14T10:00:02+00:00",
    }
]


def test_retry_replay_is_deterministic_and_exposes_policy_gaps():
    replay = build_attempt_replay(ATTEMPTS, RETRIES)
    same_events_different_input_order = build_attempt_replay(
        list(reversed(ATTEMPTS)), list(reversed(RETRIES))
    )
    assert replay == same_events_different_input_order
    assert [event["event_type"] for event in replay["timeline"]] == [
        "attempt_finished",
        "manual_retry_queued",
        "attempt_finished",
    ]
    assert replay["timeline"][1]["after_attempt"] == 1
    assert replay["timeline"][1]["queue_delay_seconds_since_failure"] == 2.0
    assert replay["retry_policy"] == {
        "mode": "manual_retry_only",
        "automatic_backoff_configured": False,
        "automatic_backoff_history": [],
        "actual_attempt_start_times_available": False,
        "lease_recovery_schedule_available": False,
    }
    assert replay["persisted_history_contiguous"] is True
    assert replay["full_timing_replay_available"] is False
    assert len(replay["replay_sha256"]) == 64


def test_retry_replay_marks_attempt_number_gaps_instead_of_filling_them():
    attempts = copy.deepcopy(ATTEMPTS)
    attempts[1]["attempt"] = 3
    replay = build_attempt_replay(attempts, RETRIES)
    assert replay["attempt_number_gaps"] == [[2, 2]]
    assert replay["persisted_history_contiguous"] is False
    assert [event["attempt"] for event in replay["timeline"] if "attempt" in event] == [
        1,
        3,
    ]


def test_retry_replay_keeps_unlinked_retry_event_visible_and_incomplete():
    early_retry = [{**RETRIES[0], "time": "2026-11-14T09:59:59+00:00"}]
    replay = build_attempt_replay(ATTEMPTS, early_retry)
    assert replay["unlinked_retry_event_ids"] == ["retry-event-1"]
    assert replay["persisted_history_contiguous"] is False


@pytest.mark.parametrize(
    ("attempts", "retries", "error"),
    [
        ([{**ATTEMPTS[0], "attempt": True}], [], "attempt_invalid"),
        ([{**ATTEMPTS[0], "status": "running"}], [], "attempt_invalid"),
        (ATTEMPTS, [{**RETRIES[0], "action": "other"}], "retry_event_invalid"),
        (ATTEMPTS, [{**RETRIES[0], "id": ""}], "retry_event_invalid"),
    ],
)
def test_retry_replay_rejects_malformed_persisted_events(attempts, retries, error):
    with pytest.raises(ValueError, match=error):
        build_attempt_replay(attempts, retries)
