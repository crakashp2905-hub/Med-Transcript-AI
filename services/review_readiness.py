"""Pre-drafting source completeness and reviewer-readiness status."""


def status(*, unverified_segments, uncertain_doses, pending_decisions):
    values = (unverified_segments, uncertain_doses, pending_decisions)
    if any(value < 0 for value in values):
        raise ValueError("invalid_review_counts")
    blocked = any(value > 0 for value in values)
    return {
        "unverified_segments": unverified_segments,
        "uncertain_doses": uncertain_doses,
        "pending_reviewer_decisions": pending_decisions,
        "drafting_blocked": blocked,
    }
