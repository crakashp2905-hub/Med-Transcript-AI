"""Versioned, failure-inclusive lexical and annotated clinical concept scoring."""

from collections import Counter
import hashlib
import json
import math

from services.evaluation import score

VERSION = "annotated_concepts_exact_v1"
WEIGHTED_VERSION = "human_impact_weighted_concept_error_v1"
PRIMARY_ENDPOINT = "failure_inclusive_normalized_word_error_rate"


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
