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


def evaluate_cases(cases, *, critical_categories):
    """Aggregate exact-concept metrics over cases with caller-declared critical categories.

    This summary never labels developer cases as clinical gold. Critical categories
    are explicit input so the metric does not embed an unreviewed clinical policy.
    """
    if not isinstance(cases, list) or not cases:
        raise ValueError("clinical_metric_cases_required")
    if not isinstance(critical_categories, (list, tuple, set)) or any(
        not isinstance(category, str) or not category
        for category in critical_categories
    ):
        raise ValueError("critical_categories_must_be_explicit")
    case_ids = [case.get("case_id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        raise ValueError("clinical_metric_case_id_required")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate_clinical_metric_case_id")

    per_case = []
    total_tp = total_fp = total_fn = critical_fn = 0
    by_category: dict[str, dict[str, int]] = {}
    case_f1 = []
    case_precision = []
    case_recall = []
    for case in cases:
        expected = case.get("expected")
        observed = case.get("observed")
        if not isinstance(expected, list) or not isinstance(observed, list):
            raise ValueError("clinical_metric_annotations_must_be_lists")
        if not isinstance(case.get("reference", ""), str) or not isinstance(
            case.get("hypothesis", ""), str
        ):
            raise ValueError("clinical_metric_transcripts_must_be_text")
        failed = bool(case.get("failed", False))
        result = evaluate(
            case.get("reference", ""),
            case.get("hypothesis", ""),
            expected,
            observed,
            failed=failed,
        )
        tp = result["concept_true_positive"]
        fp = result["concept_insertions"]
        fn = result["concept_omissions"]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        critical_fn += sum(
            row["omissions"]
            for category, row in result["by_category"].items()
            if category in critical_categories
        )
        for category, row in result["by_category"].items():
            aggregate = by_category.setdefault(
                category,
                {
                    "expected": 0,
                    "observed": 0,
                    "true_positive": 0,
                    "omissions": 0,
                    "insertions": 0,
                },
            )
            for metric in aggregate:
                aggregate[metric] += row[metric]
        has_concepts = tp + fp + fn > 0
        precision = (tp / (tp + fp) if tp + fp else 0.0) if has_concepts else None
        recall = (tp / (tp + fn) if tp + fn else 0.0) if has_concepts else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else 0.0
            if has_concepts
            else None
        )
        if has_concepts:
            case_precision.append(precision)
            case_recall.append(recall)
            case_f1.append(f1)
        per_case.append(
            {
                "case_id": case["case_id"],
                "failed": failed,
                "concept_true_positive": tp,
                "concept_insertions": fp,
                "concept_omissions": fn,
                "concept_precision": precision,
                "concept_recall": recall,
                "concept_f1": f1,
                "critical_false_negative_count": sum(
                    row["omissions"]
                    for category, row in result["by_category"].items()
                    if category in critical_categories
                ),
                "normalized_wer": result["normalized_wer"],
                "clinical_adjudication": result["clinical_adjudication"],
            }
        )

    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else None
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else None
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision is not None
        and micro_recall is not None
        and micro_precision + micro_recall
        else None
    )
    return {
        "metric_version": "clinical_concepts_per_case_micro_macro_v1",
        "case_count": len(per_case),
        "critical_categories": sorted(set(critical_categories)),
        "critical_false_negative_count": critical_fn,
        "micro": {
            "true_positive": total_tp,
            "false_positive": total_fp,
            "false_negative": total_fn,
            "precision": micro_precision,
            "recall": micro_recall,
            "f1": micro_f1,
        },
        "macro_case": {
            "precision": sum(case_precision) / len(case_precision)
            if case_precision
            else None,
            "recall": sum(case_recall) / len(case_recall) if case_recall else None,
            "f1": sum(case_f1) / len(case_f1) if case_f1 else None,
            "defined_case_count": len(case_f1),
        },
        "by_category": by_category,
        "cases": per_case,
        "primary_endpoint_unchanged": PRIMARY_ENDPOINT,
        "clinical_adjudication": "not_established_by_automated_metrics",
    }


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
