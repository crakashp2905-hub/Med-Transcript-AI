"""Versioned, failure-inclusive lexical and annotated clinical concept scoring."""
from collections import Counter
from services.evaluation import score

VERSION = "annotated_concepts_exact_v1"


def character_distance(reference, hypothesis):
    """Exact bit-vector Levenshtein, avoiding quadratic full-encounter Python loops."""
    if not reference:
        return len(hypothesis)
    masks = {}
    for i,char in enumerate(reference):
        masks[char] = masks.get(char,0) | (1<<i)
    positive,negative,result,high = ~0,0,len(reference),1<<(len(reference)-1)
    for char in hypothesis:
        equal = masks.get(char,0)
        vertical = equal | negative
        horizontal = (((equal & positive)+positive)^positive) | equal
        plus = negative | ~(horizontal | positive)
        minus = positive & horizontal
        result += bool(plus & high)-bool(minus & high)
        plus,minus = (plus<<1)|1,minus<<1
        positive,negative = minus | ~(vertical|plus),plus & vertical
    return result


def evaluate(reference, hypothesis, expected, observed, failed=False):
    """Concepts are independent annotations, never inferred gold labels from ASR."""
    if failed:
        hypothesis, observed = "", []
    def key(item):
        required = ("category", "concept", "subject", "assertion", "temporality")
        if any(not isinstance(item.get(k), str) or not item[k] for k in required):
            raise ValueError("Complete independent concept annotations are required")
        return tuple((k, item[k]) for k in sorted(item) if k not in ("evidence", "annotation_id"))
    gold, actual = Counter(map(key, expected)), Counter(map(key, observed))
    hits = sum((gold & actual).values())
    omissions, insertions = sum((gold-actual).values()), sum((actual-gold).values())
    categories = sorted({x["category"] for x in expected + observed})
    chars = len(reference.lower())
    char_edits = character_distance(reference.lower(), hypothesis.lower())
    matched, missing, added = gold & actual, gold-actual, actual-gold
    return {"metric_version": VERSION, **score(reference, hypothesis),
        "character_edits": char_edits, "character_error_rate": char_edits/chars if chars else None,
        "reference_characters": chars, "failed": failed,
        "concept_true_positive": hits, "concept_omissions": omissions, "concept_insertions": insertions,
        "concept_precision": hits/(hits+insertions) if hits+insertions else None,
        "concept_recall": hits/(hits+omissions) if hits+omissions else None,
        "by_category": {c: {"expected": sum(x["category"] == c for x in expected),
            "observed": sum(x["category"] == c for x in observed),
            "true_positive":sum(n for k,n in matched.items() if dict(k)["category"]==c),
            "omissions":sum(n for k,n in missing.items() if dict(k)["category"]==c),
            "insertions":sum(n for k,n in added.items() if dict(k)["category"]==c)} for c in categories},
        "clinical_adjudication": "not_established_by_automated_metrics"}


def coverage(intervals, duration_ms):
    if duration_ms <= 0:
        raise ValueError("Positive source duration required")
    end, covered = 0, 0
    for a, b in sorted(intervals):
        if not 0 <= a < b <= duration_ms:
            raise ValueError("Invalid original-timeline interval")
        covered += max(0, b-max(a, end))
        end = max(end, b)
    return {"covered_ms": covered, "uncovered_ms": duration_ms-covered,
        "coverage_fraction": covered/duration_ms,
        "meaning": "timestamp union, not proof of clinical content completeness"}
