"""Prospective local experiment locks; never retroactively preregister saved results."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from services.canonical import canonical_json, content_sha256
from services.engineering_status import sha256
from services.strict_json import loads


PRIMARY_ENDPOINTS = {
    "asr": "failure_inclusive_normalized_word_error_rate",
    "verification": "critical_error_miss_rate",
    "ux": "observed_active_correction_seconds_per_completed_case",
}


class PrimaryEndpoints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asr: Literal["failure_inclusive_normalized_word_error_rate"]
    verification: Literal["critical_error_miss_rate"]
    ux: Literal["observed_active_correction_seconds_per_completed_case"]


class ExperimentContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["prospective_local_experiment_v1"] = (
        "prospective_local_experiment_v1"
    )
    experiment_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    frozen_at: datetime
    cohort: Literal["development", "developer_synthetic"]
    case_ids: tuple[str, ...] = Field(min_length=2, max_length=10000)
    primary_endpoints: PrimaryEndpoints
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    maximum_normalized_wer: float = Field(default=0.05, strict=True)
    maximum_wall_seconds: int = Field(gt=0, le=86400, strict=True)
    minimum_variant_seconds: int = Field(default=1, ge=1, le=86400, strict=True)
    minimum_complete_pairs: int = Field(ge=2, strict=True)
    maximum_failure_fraction: float = Field(
        ge=0, le=1, allow_inf_nan=False, strict=True
    )
    maximum_interval_width: float = Field(gt=0, allow_inf_nan=False, strict=True)
    independent_clinical_gold: Literal[False] = False
    clinical_release: Literal[False] = False

    @model_validator(mode="after")
    def coherent(self):
        if self.maximum_normalized_wer != 0.05:
            raise ValueError("five_percent_gate_immutable")
        if self.frozen_at.tzinfo is None:
            raise ValueError("timezone_required")
        if len(set(self.case_ids)) != len(self.case_ids) or any(
            not c or len(c) > 200 for c in self.case_ids
        ):
            raise ValueError("invalid_or_duplicate_case_identity")
        if self.minimum_complete_pairs > len(self.case_ids):
            raise ValueError("pair_requirement_exceeds_predeclared_cases")
        if self.minimum_variant_seconds > self.maximum_wall_seconds:
            raise ValueError("variant_cannot_fit_declared_budget")
        return self


def freeze(path, contract, *, existing_results_present=False):
    if existing_results_present:
        raise ValueError("saved_results_cannot_be_preregistered")
    contract = ExperimentContract.model_validate(contract)
    if contract.frozen_at > datetime.now(timezone.utc):
        raise ValueError("future_freeze_time")
    path = Path(path)
    # Exclusive creation preserves earlier protocols, including unsuccessful ones.
    with path.open("x", encoding="utf-8", newline="\n") as target:
        target.write(canonical_json(contract.model_dump(mode="json")) + "\n")
    return {
        "path": path.as_posix(),
        "sha256": sha256(path),
        "contract_sha256": content_sha256(contract.model_dump(mode="json")),
    }


def load_frozen(path, expected_sha256):
    if sha256(path) != expected_sha256:
        raise ValueError("frozen_contract_changed")
    return ExperimentContract.model_validate(loads(Path(path).read_bytes()))


def variant_admission(contract, elapsed_seconds):
    """Call before starting a prospective variant; no model/provider is invoked."""
    import math

    contract = ExperimentContract.model_validate(contract)
    if (
        isinstance(elapsed_seconds, bool)
        or not isinstance(elapsed_seconds, (int, float))
        or not math.isfinite(elapsed_seconds)
        or elapsed_seconds < 0
    ):
        raise ValueError("invalid_elapsed_time")
    remaining = max(0, contract.maximum_wall_seconds - elapsed_seconds)
    return {
        "status": "admit"
        if remaining >= contract.minimum_variant_seconds
        else "stop_inconclusive",
        "remaining_seconds": remaining,
        "automatic_model_promotion": False,
    }


def assess(
    contract, *, first_result_at, rows, elapsed_seconds, complete_pairs, interval_width
):
    """Classify interpretability; do not compute accuracy or invent UX observations."""
    contract = ExperimentContract.model_validate(contract)
    if first_result_at.tzinfo is None or first_result_at < contract.frozen_at:
        raise ValueError("results_precede_prospective_lock")
    import math

    if (
        type(complete_pairs) is not int
        or not 0 <= complete_pairs <= len(contract.case_ids)
        or isinstance(elapsed_seconds, bool)
        or not isinstance(elapsed_seconds, (int, float))
        or not math.isfinite(elapsed_seconds)
        or elapsed_seconds < 0
        or interval_width is not None
        and (
            isinstance(interval_width, bool)
            or not isinstance(interval_width, (int, float))
            or not math.isfinite(interval_width)
            or interval_width < 0
        )
    ):
        raise ValueError("invalid_experiment_accounting")
    identities = [row["id"] for row in rows]
    if len(set(identities)) != len(identities) or not set(identities) <= set(
        contract.case_ids
    ):
        raise ValueError("unknown_or_duplicate_result_case")
    if any(
        row["status"] not in ("succeeded", "failed", "timed_out", "not_run")
        for row in rows
    ):
        raise ValueError("unknown_result_status")
    failures = sum(row["status"] != "succeeded" for row in rows)
    if complete_pairs > len(rows) - failures:
        raise ValueError("complete_pairs_exceed_successful_cases")
    reasons = []
    if set(identities) != set(contract.case_ids):
        reasons.append("missing_predeclared_cases")
    if failures / len(contract.case_ids) > contract.maximum_failure_fraction:
        reasons.append("failure_budget_exceeded")
    if elapsed_seconds > contract.maximum_wall_seconds:
        reasons.append("wall_budget_exceeded")
    if complete_pairs < contract.minimum_complete_pairs:
        reasons.append("insufficient_complete_pairs")
    if interval_width is None or interval_width > contract.maximum_interval_width:
        reasons.append("effect_unresolved")
    return {
        "status": "inconclusive" if reasons else "eligible_for_prespecified_analysis",
        "reasons": reasons,
        "failed_or_unperformed_cases": failures,
        "predeclared_cases": len(contract.case_ids),
        "reported_cases": len(rows),
        "contract_sha256": content_sha256(contract.model_dump(mode="json")),
        "case_statuses": rows,
        "automatic_model_promotion": False,
        "independent_clinical_gold": False,
        "clinical_release": False,
        "limitations": "Interpretability accounting only; no model score or human UX observation is inferred.",
    }
