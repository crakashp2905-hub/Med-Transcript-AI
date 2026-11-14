"""Shared failure-inclusive evaluation envelope and evidence-class contract."""

import time
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from services.canonical import content_sha256

EVIDENCE_CLASSES = {
    "software_transport_test",
    "model_inference_result",
    "synthetic_rule_test",
    "public_mock_asr_test",
    "independent_clinical_annotation",
    "historical_model_replay",
    "unverified",
}
CASE_STATUSES = {"succeeded", "failed", "timed_out", "aborted", "not_run"}


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dataset_id: str = Field(min_length=1, max_length=120)
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    split: str = Field(min_length=1, max_length=40)
    model_id: str = Field(min_length=1, max_length=160)
    model_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime: dict
    hardware: dict
    evidence_class: str
    wall_seconds: float = Field(ge=0, allow_inf_nan=False)
    limitations: list[str] = Field(min_length=1, max_length=100)


def build_envelope(*, provenance, manifest_case_ids, result_rows):
    """Require exactly one explicit status row per manifest case identity."""
    try:
        frozen = Provenance.model_validate(provenance)
    except ValidationError as error:
        raise ValueError("evaluation_provenance_invalid") from error
    if frozen.evidence_class not in EVIDENCE_CLASSES:
        raise ValueError("evaluation_evidence_class_invalid")
    if (
        frozen.evidence_class == "independent_clinical_annotation"
        and frozen.model_digest is not None
    ):
        raise ValueError("annotation_evidence_cannot_claim_model_digest")
    if not isinstance(manifest_case_ids, (list, tuple)) or not manifest_case_ids:
        raise ValueError("evaluation_manifest_cases_required")
    expected = list(manifest_case_ids)
    if any(not isinstance(case_id, str) or not case_id for case_id in expected) or len(
        set(expected)
    ) != len(expected):
        raise ValueError("evaluation_manifest_case_ids_invalid")
    if not isinstance(result_rows, list):
        raise ValueError("evaluation_result_rows_required")
    observed, counts = {}, {status: 0 for status in CASE_STATUSES}
    for row in result_rows:
        if not isinstance(row, dict):
            raise ValueError("evaluation_result_row_invalid")
        case_id, status = row.get("case_id"), row.get("status")
        if (
            not isinstance(case_id, str)
            or case_id not in expected
            or case_id in observed
            or status not in CASE_STATUSES
        ):
            raise ValueError("evaluation_case_identity_or_status_invalid")
        observed[case_id] = row
        counts[status] += 1
    missing = sorted(set(expected) - set(observed))
    if missing:
        raise ValueError("evaluation_cases_unaccounted")
    cases = [observed[case_id] for case_id in expected]
    envelope = {
        "schema_version": "failure_inclusive_evaluation_v1",
        "run_id": str(uuid4()),
        "provenance": frozen.model_dump(mode="json"),
        "case_count": len(expected),
        "case_status_counts": counts,
        "cases": cases,
        "all_manifest_cases_accounted": True,
        "failure_inclusive_denominator": len(expected),
        "clinical_release_authorized": False,
    }
    envelope["envelope_sha256"] = content_sha256(envelope)
    return envelope


def run_cases(*, provenance, manifest_case_ids, evaluate_case):
    """Run each manifest ID once; retain failed cases in the result denominator.

    The evaluator returns a JSON-compatible dict. Exceptions are represented as
    opaque failed statuses; exception text is omitted to avoid leaking data.
    """
    rows = []
    started = time.perf_counter()
    for case_id in manifest_case_ids:
        case_started = time.perf_counter()
        try:
            result = evaluate_case(case_id)
            if not isinstance(result, dict):
                raise ValueError("evaluation_case_result_invalid")
            if {"case_id", "status", "wall_seconds"} & result.keys():
                raise ValueError("evaluation_case_result_reserved_key")
            rows.append({**result, "case_id": case_id, "status": "succeeded"})
        except TimeoutError:
            rows.append({"case_id": case_id, "status": "timed_out"})
        except Exception:
            rows.append({"case_id": case_id, "status": "failed"})
        rows[-1]["wall_seconds"] = max(0.0, time.perf_counter() - case_started)
    envelope = build_envelope(
        provenance={**provenance, "wall_seconds": time.perf_counter() - started},
        manifest_case_ids=manifest_case_ids,
        result_rows=rows,
    )
    return envelope
