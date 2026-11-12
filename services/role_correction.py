"""Source-linked speaker-role correction preview."""


def preview(turns, corrections):
    if not isinstance(turns, list) or not isinstance(corrections, dict):
        raise ValueError("turns_and_corrections_required")
    changes = []
    for turn in turns:
        speaker = turn.get("speaker")
        if speaker in corrections:
            changes.append(
                {
                    "turn_id": turn.get("id"),
                    "source_ref": turn.get("source_ref"),
                    "from": turn.get("role"),
                    "to": corrections[speaker],
                }
            )
    return {
        "changes": changes,
        "uncertain_speakers": sorted(corrections),
        "approval_required": bool(changes),
    }
