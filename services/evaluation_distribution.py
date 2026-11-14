"""Worst-slice and consultation-level distribution summaries."""


def _quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def summarize(cases, *, case_id="sample_id", group_id="group_id", dimensions=None):
    """Summarize WER distribution per case and worst annotated subgroup.

    Failed rows stay in all denominators and use their supplied edits (normally
    full-reference deletions). Groups with no reference words remain visible.
    """
    if not isinstance(cases, list) or not cases:
        raise ValueError("evaluation_distribution_cases_required")
    dimensions = dimensions or (
        "speaker_role",
        "noise_condition",
        "reference_uncertain",
    )
    seen = set()
    rates = []
    grouped = {group_id: {}}
    for row in cases:
        if not isinstance(row, dict):
            raise ValueError("evaluation_distribution_case_invalid")
        identity = row.get(case_id)
        words, edits = row.get("reference_words"), row.get("normalized_edits")
        hypothesis_words = row.get("hypothesis_words")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in seen
            or type(words) is not int
            or words < 0
            or type(edits) is not int
            or edits < 0
            or hypothesis_words is not None
            and (type(hypothesis_words) is not int or hypothesis_words < 0)
            or hypothesis_words is not None
            and edits > max(words, hypothesis_words)
        ):
            raise ValueError("evaluation_distribution_case_metrics_invalid")
        seen.add(identity)
        rate = edits / words if words else None
        if rate is not None:
            rates.append(rate)
        group = row.get(group_id, "unspecified")
        grouped[group_id].setdefault(str(group), []).append(row)
    pooled_words = sum(row["reference_words"] for row in cases)
    pooled_edits = sum(row["normalized_edits"] for row in cases)
    worst_slices = {}
    for dimension in dimensions:
        slices = {}
        for row in cases:
            label = row.get(dimension, "unlabeled")
            slices.setdefault(str(label), []).append(row)
        summary = {
            label: {
                "case_count": len(rows),
                "failed_case_count": sum(row.get("status") == "failed" for row in rows),
                "reference_words": sum(row["reference_words"] for row in rows),
                "normalized_edits": sum(row["normalized_edits"] for row in rows),
                "normalized_wer": (
                    sum(row["normalized_edits"] for row in rows)
                    / sum(row["reference_words"] for row in rows)
                    if sum(row["reference_words"] for row in rows)
                    else None
                ),
            }
            for label, rows in slices.items()
        }
        eligible = [
            (label, row["normalized_wer"])
            for label, row in summary.items()
            if row["normalized_wer"] is not None
        ]
        worst_slices[dimension] = {
            "slices": summary,
            "worst_slice": max(eligible, key=lambda item: (item[1], item[0]))[0]
            if eligible
            else None,
        }
    by_group = {
        label: {
            "case_count": len(rows),
            "failed_case_count": sum(row.get("status") == "failed" for row in rows),
            "reference_words": sum(row["reference_words"] for row in rows),
            "normalized_edits": sum(row["normalized_edits"] for row in rows),
            "normalized_wer": (
                sum(row["normalized_edits"] for row in rows)
                / sum(row["reference_words"] for row in rows)
                if sum(row["reference_words"] for row in rows)
                else None
            ),
        }
        for label, rows in grouped[group_id].items()
    }
    return {
        "schema_version": "evaluation_distribution_v1",
        "case_count": len(cases),
        "failed_case_count": sum(row.get("status") == "failed" for row in cases),
        "pooled_normalized_wer": pooled_edits / pooled_words if pooled_words else None,
        "consultation_wer_distribution": {
            "defined_case_count": len(rates),
            "p50": _quantile(rates, 0.50),
            "p95": _quantile(rates, 0.95),
            "quantile_method": "linear_interpolation_type_7",
        },
        "by_consultation": by_group,
        "worst_slices": worst_slices,
        "failure_inclusive": True,
    }
