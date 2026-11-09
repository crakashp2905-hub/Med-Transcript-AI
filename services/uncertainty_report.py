"""Uncertainty report with exact denominators and paired interval metadata."""


def report(*, correct, total, interval_low, interval_high, synthetic=False):
    if total < 0 or correct < 0 or correct > total:
        raise ValueError('invalid_denominator')
    if interval_low < 0 or interval_high < interval_low:
        raise ValueError('invalid_interval')
    return {'correct': correct, 'total': total, 'interval': [interval_low, interval_high],
            'denominator_exact': True, 'paired': True,
            'evidence_class': 'mechanistic_synthetic' if synthetic else 'development'}
