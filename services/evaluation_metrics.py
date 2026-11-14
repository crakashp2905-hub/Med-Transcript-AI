"""Deterministic text metrics using the frozen ASR word normalization."""

from services.asr.evaluation_contract import NORMALIZATION_PATTERN


def _distance(left, right):
    previous = list(range(len(right) + 1))
    for row, left_item in enumerate(left, 1):
        current = [row]
        for column, right_item in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def _word_alignment(reference, hypothesis):
    rows, columns = len(reference), len(hypothesis)
    if rows * columns > 4_000_000:
        raise ValueError("evaluation_alignment_size_limit_exceeded")
    table = [[0] * (columns + 1) for _ in range(rows + 1)]
    for i in range(rows + 1):
        table[i][0] = i
    for j in range(columns + 1):
        table[0][j] = j
    for i in range(1, rows + 1):
        for j in range(1, columns + 1):
            table[i][j] = min(
                table[i - 1][j] + 1,
                table[i][j - 1] + 1,
                table[i - 1][j - 1] + (reference[i - 1] != hypothesis[j - 1]),
            )
    substitutions = deletions = insertions = 0
    i, j = rows, columns
    while i or j:
        if (
            i
            and j
            and reference[i - 1] == hypothesis[j - 1]
            and table[i][j] == table[i - 1][j - 1]
        ):
            i -= 1
            j -= 1
        elif i and j and table[i][j] == table[i - 1][j - 1] + 1:
            substitutions += 1
            i -= 1
            j -= 1
        elif i and table[i][j] == table[i - 1][j] + 1:
            deletions += 1
            i -= 1
        else:
            insertions += 1
            j -= 1
    return substitutions, deletions, insertions


def score_text(reference, hypothesis):
    """Return WER, CER and S/D/I; empty references have undefined rates."""
    if not isinstance(reference, str) or not isinstance(hypothesis, str):
        raise ValueError("evaluation_text_must_be_string")
    ref_words = __import__("re").findall(NORMALIZATION_PATTERN, reference.lower())
    hyp_words = __import__("re").findall(NORMALIZATION_PATTERN, hypothesis.lower())
    if max(len(ref_words), len(hyp_words)) > 10_000:
        raise ValueError("evaluation_token_limit_exceeded")
    substitutions, deletions, insertions = _word_alignment(ref_words, hyp_words)
    # Character normalization is explicit: lowercase alphanumerics, preserving
    # digits and decimal points so medication strengths remain distinguishable.
    import re

    ref_chars = re.sub(r"[^a-z0-9.]", "", reference.lower())
    hyp_chars = re.sub(r"[^a-z0-9.]", "", hypothesis.lower())
    if len(ref_chars) * len(hyp_chars) > 4_000_000:
        raise ValueError("evaluation_character_alignment_size_limit_exceeded")
    edits = substitutions + deletions + insertions
    return {
        "normalization": "lowercase_words_preserve_decimals_units_negation_v1",
        "reference_words": len(ref_words),
        "hypothesis_words": len(hyp_words),
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "word_edits": edits,
        "wer": edits / len(ref_words) if ref_words else None,
        "reference_characters": len(ref_chars),
        "character_edits": _distance(ref_chars, hyp_chars),
        "cer": _distance(ref_chars, hyp_chars) / len(ref_chars) if ref_chars else None,
    }
