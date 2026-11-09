"""Controlled transcript perturbation case definitions."""

PERTURBATIONS = ('surface_paraphrase', 'speaker_swap', 'omitted_clause', 'reversed_temporal', 'misleading_instruction')


def cases(source):
    if not isinstance(source, str) or not source:
        raise ValueError('source_required')
    return [{'kind': kind, 'source': source, 'source_untrusted': True} for kind in PERTURBATIONS]
