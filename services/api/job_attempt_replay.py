"""Deterministic, limitation-aware replay of persisted job retry events."""

import hashlib
import json
from datetime import datetime


ATTEMPT_STATUSES = {"abandoned", "failed", "succeeded"}


def _time(value):
    if not isinstance(value, str):
        raise ValueError("job_replay_timestamp_required")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("job_replay_timestamp_invalid") from exc


def build_attempt_replay(attempts, retry_events):
    """Replay attempt completions and manual retry requests in stable order.

    The application has no automatic retry/backoff scheduler. Its callers may
    request a retry explicitly, which is recorded in the audit chain. Attempt
    start timestamps and lease-recovery scheduling are not persisted, so this
    projection never fabricates them.
    """
    if not isinstance(attempts, list) or not isinstance(retry_events, list):
        raise ValueError("job_replay_inputs_must_be_lists")

    timeline = []
    seen_attempts = set()
    ordered_attempts = sorted(attempts, key=lambda row: row["attempt"])
    for row in ordered_attempts:
        number = row.get("attempt")
        status = row.get("status")
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or number < 1
            or number in seen_attempts
            or status not in ATTEMPT_STATUSES
        ):
            raise ValueError("job_replay_attempt_invalid")
        seen_attempts.add(number)
        timestamp = row.get("finished_at")
        _time(timestamp)
        timeline.append(
            {
                "event_type": "attempt_finished",
                "time": timestamp,
                "attempt": number,
                "status": status,
                "error_code": row.get("error_code"),
            }
        )

    seen_retry_ids = set()
    unlinked_retries = []
    retry_events = sorted(
        retry_events, key=lambda row: (_time(row.get("time")), row.get("id", ""))
    )
    used_failures = set()
    failed_attempts = [
        row for row in ordered_attempts if row.get("status") in {"failed", "abandoned"}
    ]
    for row in retry_events:
        retry_id = row.get("id")
        if (
            not isinstance(retry_id, str)
            or not retry_id
            or retry_id in seen_retry_ids
            or row.get("action") != "transcription_retry_queued"
        ):
            raise ValueError("job_replay_retry_event_invalid")
        seen_retry_ids.add(retry_id)
        timestamp = row.get("time")
        retry_time = _time(timestamp)
        candidates = [
            failed
            for failed in failed_attempts
            if failed["attempt"] not in used_failures
            and _time(failed["finished_at"]) <= retry_time
        ]
        retry_event = {
            "event_type": "manual_retry_queued",
            "time": timestamp,
            "event_id": retry_id,
            "after_attempt": None,
            "queue_delay_seconds_since_failure": None,
        }
        if candidates:
            failed = candidates[-1]
            used_failures.add(failed["attempt"])
            retry_event["after_attempt"] = failed["attempt"]
            retry_event["queue_delay_seconds_since_failure"] = (
                retry_time - _time(failed["finished_at"])
            ).total_seconds()
        else:
            unlinked_retries.append(retry_id)
        timeline.append(retry_event)

    timeline.sort(
        key=lambda row: (
            _time(row["time"]),
            0 if row["event_type"] == "attempt_finished" else 1,
            row.get("attempt", 0),
            row.get("event_id", ""),
        )
    )
    numbers = sorted(seen_attempts)
    gaps = [
        [previous + 1, current - 1]
        for previous, current in zip(numbers, numbers[1:])
        if current > previous + 1
    ]
    document = {
        "schema_version": "job_attempt_replay_v1",
        "timeline": timeline,
        "attempt_number_gaps": gaps,
        "unlinked_retry_event_ids": unlinked_retries,
        "retry_policy": {
            "mode": "manual_retry_only",
            "automatic_backoff_configured": False,
            "automatic_backoff_history": [],
            "actual_attempt_start_times_available": False,
            "lease_recovery_schedule_available": False,
        },
        "persisted_history_contiguous": not gaps and not unlinked_retries,
        "full_timing_replay_available": False,
        "limitations": [
            "Only persisted attempt completions and manual retry audit events are replayed.",
            "Attempt start times and automatic lease-recovery timing are not stored.",
            "No automatic backoff policy is configured or inferred.",
        ],
    }
    canonical = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    document["replay_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return document
