"""Consent revocation guard for every processing stage."""

STAGES = (
    "capture",
    "upload",
    "normalization",
    "diarization",
    "asr",
    "drafting",
    "verification",
    "publication",
)


def evaluate(*, revoked, stage):
    if stage not in STAGES:
        raise ValueError("unknown_stage")
    return {
        "stage": stage,
        "revoked": revoked,
        "allowed": not revoked,
        "publication_blocked": revoked,
    }
