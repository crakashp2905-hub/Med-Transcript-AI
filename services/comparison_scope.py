"""Scope-safe comparison preparation for datasets and model variants."""


def prepare(rows):
    if not isinstance(rows, list):
        raise ValueError("comparison_rows_required")
    scopes = {
        (row.get("dataset_id"), row.get("task_scope"), row.get("evaluation_scope"))
        for row in rows
    }
    if len(scopes - {(None, None, None)}) > 1:
        raise ValueError("cross_dataset_comparison_forbidden")
    visible = []
    for row in rows:
        if not row.get("candidate_id"):
            raise ValueError("comparison_candidate_id_required")
        item = dict(row)
        item["rankable"] = (
            item.get("status") == "completed" and item.get("normalized_wer") is not None
        )
        if not item["rankable"]:
            item["rank"] = None
        visible.append(item)
    ranked = sorted(
        (r for r in visible if r["rankable"]),
        key=lambda r: (r["normalized_wer"], r["candidate_id"]),
    )
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
    return {
        "schema_version": "comparison_scope_v1",
        "scope": next(iter(scopes)) if scopes else (None, None, None),
        "rows": visible,
        "ranked_candidates": [r["candidate_id"] for r in ranked],
        "failed_or_unranked_visible": any(not r["rankable"] for r in visible),
        "clinical_acceptance": False,
        "real_patient_release_authorized": False,
    }
