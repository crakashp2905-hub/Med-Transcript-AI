"""Speaker review interaction plan."""


def plan(turns):
    if not isinstance(turns, list):
        raise ValueError("turns_required")
    return {
        "exemplar_playback": True,
        "batch_confirm_ids": [
            turn["id"] for turn in turns if turn.get("ambiguous") is False
        ],
        "isolated_ambiguous_ids": [
            turn["id"] for turn in turns if turn.get("ambiguous") is True
        ],
        "approval_required": True,
    }
