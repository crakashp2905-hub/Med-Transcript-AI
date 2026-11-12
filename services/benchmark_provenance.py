"""Fail-closed provenance checks for complete and interrupted benchmark runs."""


def validate_run(report, *, expected_manifest_sha256=None):
    if (
        expected_manifest_sha256
        and report.get("manifest_sha256") != expected_manifest_sha256
    ):
        raise ValueError("benchmark_manifest_hash_mismatch")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("benchmark_cases_missing")
    seen = set()
    counts = {"completed": 0, "failed": 0, "partial": 0}
    for case in cases:
        cid = case.get("id") or case.get("sample_id")
        if not cid or cid in seen:
            raise ValueError("benchmark_case_duplicate_or_missing_id")
        seen.add(cid)
        status = case.get("status")
        if case.get("failed") is True or status in (
            "failed",
            "runtime_failed",
            "timed_out",
        ):
            counts["failed"] += 1
        elif status in ("partial", "incomplete") or case.get("complete") is False:
            counts["partial"] += 1
        else:
            counts["completed"] += 1
    return {
        "case_count": len(cases),
        "counts": counts,
        "complete": bool(report.get("complete") is True and counts["partial"] == 0),
        "resumed_from": report.get("resumed_from"),
        "retry_ancestry_preserved": "resumed_from" in report,
        "real_patient_release_authorized": False,
    }
