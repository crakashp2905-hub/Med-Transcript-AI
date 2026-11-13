"""Descriptive uncertainty summaries with explicit non-calibration labels."""


def report(
    *, correct, total, interval_low, interval_high, synthetic=False, paired=False
):
    if (
        type(correct) is not int
        or type(total) is not int
        or total < 0
        or correct < 0
        or correct > total
    ):
        raise ValueError("invalid_denominator")
    if (
        not isinstance(interval_low, (int, float))
        or not isinstance(interval_high, (int, float))
        or interval_low < 0
        or interval_high < interval_low
        or interval_high > 1
    ):
        raise ValueError("invalid_interval")
    if type(paired) is not bool:
        raise ValueError("invalid_pairing_declaration")
    return {
        "correct": correct,
        "total": total,
        "interval": [interval_low, interval_high],
        "denominator_exact": True,
        "paired": paired,
        "pairing_status": "caller_declared" if paired else "not_established",
        "uncertainty_kind": "descriptive_interval_not_asr_confidence",
        "calibrated": False,
        "probability_estimate": None,
        "evidence_class": "mechanistic_synthetic" if synthetic else "development",
    }
