"""Keep automatic diarization experimental until score and review gates pass."""


def admission(*, score, maximum_der, human_review_complete):
    if maximum_der <= 0 or maximum_der >= 1:
        raise ValueError("invalid_der_threshold")
    passed = score <= maximum_der and human_review_complete is True
    return {
        "status": "eligible_for_experimental_review" if passed else "experimental_only",
        "score": score,
        "maximum_der": maximum_der,
        "human_review_complete": bool(human_review_complete),
        "clinical_acceptance": False,
        "automatic_role_promotion": False,
    }
