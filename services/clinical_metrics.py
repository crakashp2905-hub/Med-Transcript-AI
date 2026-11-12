"""Versioned, failure-inclusive lexical and annotated clinical concept scoring."""

from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
import math
import re

from services.evaluation import score

VERSION = "annotated_concepts_exact_v1"
WEIGHTED_VERSION = "human_impact_weighted_concept_error_v1"
PRIMARY_ENDPOINT = "failure_inclusive_normalized_word_error_rate"
WORD_SPAN = re.compile(r"\d+(?:\.\d+)?|[a-z]+(?:['-][a-z]+)*", re.IGNORECASE)


def character_distance(reference, hypothesis):
    """Exact bit-vector Levenshtein, avoiding quadratic full-encounter Python loops."""
    if not reference:
        return len(hypothesis)
    masks = {}
    for i, char in enumerate(reference):
        masks[char] = masks.get(char, 0) | (1 << i)
    positive, negative, result, high = ~0, 0, len(reference), 1 << (len(reference) - 1)
    for char in hypothesis:
        equal = masks.get(char, 0)
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        plus = negative | ~(horizontal | positive)
        minus = positive & horizontal
        result += bool(plus & high) - bool(minus & high)
        plus, minus = (plus << 1) | 1, minus << 1
        positive, negative = minus | ~(vertical | plus), plus & vertical
    return result


def surface_form_diagnostics(reference, hypothesis):
    """Separate case and aligned punctuation-boundary changes from lexical WER."""
    reference_spans = list(WORD_SPAN.finditer(reference))
    hypothesis_spans = list(WORD_SPAN.finditer(hypothesis))
    blocks = SequenceMatcher(
        a=[span.group().lower() for span in reference_spans],
        b=[span.group().lower() for span in hypothesis_spans],
        autojunk=False,
    ).get_matching_blocks()
    aligned = [
        (i, j)
        for block in blocks
        for i, j in zip(
            range(block.a, block.a + block.size),
            range(block.b, block.b + block.size),
        )
    ]
    case_mismatches = sum(
        reference_spans[i].group() != hypothesis_spans[j].group() for i, j in aligned
    )

    def punctuation(text):
        return "".join(character for character in text if not character.isalnum())

    boundaries = []
    if aligned and aligned[0] == (0, 0):
        boundaries.append(
            (
                punctuation(reference[: reference_spans[0].start()]),
                punctuation(hypothesis[: hypothesis_spans[0].start()]),
            )
        )
    for (ref_i, hyp_i), (next_ref_i, next_hyp_i) in zip(aligned, aligned[1:]):
        if next_ref_i == ref_i + 1 and next_hyp_i == hyp_i + 1:
            boundaries.append(
                (
                    punctuation(
                        reference[
                            reference_spans[ref_i].end() : reference_spans[
                                next_ref_i
                            ].start()
                        ]
                    ),
                    punctuation(
                        hypothesis[
                            hypothesis_spans[hyp_i].end() : hypothesis_spans[
                                next_hyp_i
                            ].start()
                        ]
                    ),
                )
            )
    if aligned and aligned[-1] == (len(reference_spans) - 1, len(hypothesis_spans) - 1):
        ref_end = reference_spans[-1].end()
        hyp_end = hypothesis_spans[-1].end()
        boundaries.append(
            (punctuation(reference[ref_end:]), punctuation(hypothesis[hyp_end:]))
        )

    punctuation_mismatches = sum(left != right for left, right in boundaries)
    return {
        "method": "case_and_punctuation_on_exact_normalized_word_alignment_v1",
        "aligned_normalized_words": len(aligned),
        "case_mismatches": case_mismatches,
        "case_mismatch_rate": case_mismatches / len(aligned) if aligned else None,
        "punctuation_boundaries_compared": len(boundaries),
        "punctuation_boundary_mismatches": punctuation_mismatches,
        "punctuation_boundary_mismatch_rate": (
            punctuation_mismatches / len(boundaries) if boundaries else None
        ),
        "lexical_endpoint_unchanged": PRIMARY_ENDPOINT,
        "limitations": [
            "Surface diagnostics compare only exact normalized word alignments.",
            "They do not change normalized WER or determine clinical correctness.",
        ],
    }


def concept_key(item):
    """Canonical exact-match key; evidence coordinates and IDs are provenance."""
    required = ("category", "concept", "subject", "assertion", "temporality")
    if any(not isinstance(item.get(k), str) or not item[k] for k in required):
        raise ValueError("Complete independent concept annotations are required")
    return json.dumps(
        {k: v for k, v in item.items() if k not in ("evidence", "annotation_id")},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def weighted_concepts(expected, observed, impact_weights, failed=False):
    """Score weighted concept errors using explicit, caller-supplied weights.

    The registry must cover every expected and observed exact concept key. This
    function assigns no weights and does not designate annotations as clinical
    gold; the caller must supply independently reviewed annotations and weights.
    """
    if failed:
        observed = []
    if not isinstance(impact_weights, dict) or not impact_weights:
        raise ValueError("independent_impact_weight_registry_required")
    gold, actual = (
        Counter(map(concept_key, expected)),
        Counter(map(concept_key, observed)),
    )
    all_keys = set(gold) | set(actual)
    if set(impact_weights) != all_keys:
        raise ValueError("impact_weight_registry_must_cover_exact_concepts")
    for key, weight in impact_weights.items():
        if (
            not isinstance(key, str)
            or not isinstance(weight, (int, float))
            or isinstance(weight, bool)
            or isinstance(weight, float)
            and not math.isfinite(weight)
            or weight <= 0
        ):
            raise ValueError("impact_weights_must_be_positive_finite_numbers")
    matches = gold & actual
    omissions = gold - actual
    insertions = actual - gold
    matched_weight = sum(impact_weights[key] * count for key, count in matches.items())
    omitted_weight = sum(
        impact_weights[key] * count for key, count in omissions.items()
    )
    inserted_weight = sum(
        impact_weights[key] * count for key, count in insertions.items()
    )
    expected_weight = sum(impact_weights[key] * count for key, count in gold.items())
    observed_weight = sum(impact_weights[key] * count for key, count in actual.items())
    weight_digest = hashlib.sha256(
        json.dumps(
            impact_weights, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    result = {
        "metric_version": WEIGHTED_VERSION,
        "weight_registry_sha256": weight_digest,
        "weighted_concept_matches": matched_weight,
        "weighted_concept_omissions": omitted_weight,
        "weighted_concept_insertions": inserted_weight,
        "weighted_concept_error_mass": omitted_weight + inserted_weight,
        "weighted_concept_error_rate": (
            (omitted_weight + inserted_weight) / expected_weight
            if expected_weight
            else None
        ),
        "weighted_concept_precision": (
            matched_weight / observed_weight if observed_weight else None
        ),
        "weighted_concept_recall": (
            matched_weight / expected_weight if expected_weight else None
        ),
        "primary_endpoint_unchanged": PRIMARY_ENDPOINT,
        "clinical_adjudication": "not_established_by_metric_alone",
    }
    return result


def evaluate(
    reference, hypothesis, expected, observed, failed=False, impact_weights=None
):
    """Concepts are independent annotations, never inferred gold labels from ASR."""
    if failed:
        hypothesis, observed = "", []

    gold, actual = (
        Counter(map(concept_key, expected)),
        Counter(map(concept_key, observed)),
    )
    hits = sum((gold & actual).values())
    omissions, insertions = sum((gold - actual).values()), sum((actual - gold).values())
    categories = sorted({x["category"] for x in expected + observed})
    chars = len(reference.lower())
    char_edits = character_distance(reference.lower(), hypothesis.lower())
    matched, missing, added = gold & actual, gold - actual, actual - gold
    lexical = score(reference, hypothesis)
    result = {
        "metric_version": VERSION,
        **lexical,
        "surface_form_diagnostics": surface_form_diagnostics(reference, hypothesis),
        "raw_wer": lexical["raw_edits"] / lexical["raw_reference_words"]
        if lexical["raw_reference_words"]
        else None,
        "normalized_wer": lexical["normalized_edits"] / lexical["reference_words"]
        if lexical["reference_words"]
        else None,
        "character_edits": char_edits,
        "character_error_rate": char_edits / chars if chars else None,
        "reference_characters": chars,
        "raw_cer": char_edits / chars if chars else None,
        "normalized_cer": char_edits / chars if chars else None,
        "failed": failed,
        "concept_true_positive": hits,
        "concept_omissions": omissions,
        "concept_insertions": insertions,
        "concept_precision": hits / (hits + insertions) if hits + insertions else None,
        "concept_recall": hits / (hits + omissions) if hits + omissions else None,
        "by_category": {
            c: {
                "expected": sum(x["category"] == c for x in expected),
                "observed": sum(x["category"] == c for x in observed),
                "true_positive": sum(
                    n for k, n in matched.items() if json.loads(k)["category"] == c
                ),
                "omissions": sum(
                    n for k, n in missing.items() if json.loads(k)["category"] == c
                ),
                "insertions": sum(
                    n for k, n in added.items() if json.loads(k)["category"] == c
                ),
            }
            for c in categories
        },
        "clinical_adjudication": "not_established_by_automated_metrics",
    }
    if impact_weights is not None:
        result["weighted_secondary_endpoint"] = weighted_concepts(
            expected, observed, impact_weights, failed=failed
        )
    return result


def coverage(intervals, duration_ms):
    if duration_ms <= 0:
        raise ValueError("Positive source duration required")
    end, covered = 0, 0
    for a, b in sorted(intervals):
        if not 0 <= a < b <= duration_ms:
            raise ValueError("Invalid original-timeline interval")
        covered += max(0, b - max(a, end))
        end = max(end, b)
    return {
        "covered_ms": covered,
        "uncovered_ms": duration_ms - covered,
        "coverage_fraction": covered / duration_ms,
        "meaning": "timestamp union, not proof of clinical content completeness",
    }
