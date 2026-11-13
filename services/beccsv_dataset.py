"""Validate versioned synthetic BECCSV development scenarios and their lock."""

import hashlib
import json
from pathlib import Path


def generate_synthetic_scenarios():
    """Generate deterministic synthetic counterexamples for graph development."""
    medication_pairs = (
        ("warfarin", "2 mg each evening", "500 mg twice daily"),
        ("metformin", "500 mg twice daily", "2 mg each evening"),
    )
    scenarios = []
    for index, (drug, source_dose, swapped_dose) in enumerate(medication_pairs, 1):
        quote = f"I take {drug} {source_dose}."
        scenarios.append(
            {
                "case_id": f"generated-dose-swap-{index}",
                "synthetic": True,
                "clinical_gold": False,
                "turns": [{"speaker": "patient", "text": quote}],
                "source_fact": {
                    "fact_id": "source-1",
                    "quote": quote,
                    "concept": drug,
                    "dose": source_dose,
                    "severity": "critical",
                },
                "note_claim": {
                    "claim_id": "claim-1",
                    "source_fact_ids": ["source-1"],
                    "concept": drug,
                    "dose": swapped_dose,
                },
                "expected_mismatch": "relation_mismatch",
            }
        )
    scenarios.extend(
        [
            {
                "case_id": "generated-negation-reversal",
                "synthetic": True,
                "clinical_gold": False,
                "turns": [{"speaker": "patient", "text": "I do not have a fever."}],
                "source_fact": {
                    "fact_id": "source-1",
                    "quote": "I do not have a fever",
                    "concept": "fever",
                    "polarity": "negated",
                    "severity": "critical",
                },
                "note_claim": {
                    "claim_id": "claim-1",
                    "source_fact_ids": ["source-1"],
                    "concept": "fever",
                    "polarity": "affirmed",
                },
                "expected_mismatch": "polarity_mismatch",
            },
            {
                "case_id": "generated-family-subject-swap",
                "synthetic": True,
                "clinical_gold": False,
                "turns": [{"speaker": "patient", "text": "My mother has diabetes."}],
                "source_fact": {
                    "fact_id": "source-1",
                    "quote": "My mother has diabetes",
                    "concept": "diabetes",
                    "subject": "mother",
                    "severity": "high",
                },
                "note_claim": {
                    "claim_id": "claim-1",
                    "source_fact_ids": ["source-1"],
                    "concept": "diabetes",
                    "subject": "patient",
                },
                "expected_mismatch": "subject_mismatch",
            },
            {
                "case_id": "generated-temporal-flip",
                "synthetic": True,
                "clinical_gold": False,
                "turns": [
                    {
                        "speaker": "patient",
                        "text": "I had a cough last week, but it has resolved.",
                    }
                ],
                "source_fact": {
                    "fact_id": "source-1",
                    "quote": "I had a cough last week",
                    "concept": "cough",
                    "temporality": "historical_resolved",
                    "severity": "high",
                },
                "note_claim": {
                    "claim_id": "claim-1",
                    "source_fact_ids": ["source-1"],
                    "concept": "cough",
                    "temporality": "current",
                },
                "expected_mismatch": "temporal_mismatch",
            },
        ]
    )
    return scenarios


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def validate_manifest(manifest):
    if (
        manifest.get("schema_version") != "beccsv_synthetic_dev_v1"
        or manifest.get("dataset_id") != "beccsv-synthetic-dev-v1"
        or manifest.get("synthetic") is not True
        or manifest.get("clinical_gold") is not False
        or manifest.get("independent_adjudication") is not False
        or manifest.get("acceptance_use_authorized") is not False
        or manifest.get("real_patient_data") is not False
    ):
        raise ValueError("beccsv_dataset_scope_invalid")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not 6 <= len(cases) <= 100:
        raise ValueError("beccsv_dataset_case_count_invalid")
    case_ids = set()
    fact_count = claim_count = 0
    for case in cases:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise ValueError("beccsv_dataset_case_id_invalid")
        case_ids.add(case_id)
        turns = case.get("turns")
        if not isinstance(turns, list) or len(turns) < 3:
            raise ValueError("beccsv_dataset_turns_invalid")
        if any(
            turn.get("speaker") not in {"patient", "clinician", "caregiver"}
            or not isinstance(turn.get("text"), str)
            or not turn["text"].strip()
            for turn in turns
        ):
            raise ValueError("beccsv_dataset_turn_invalid")
        transcript = " ".join(turn["text"] for turn in turns)
        facts = case.get("source_facts")
        claims = case.get("note_claims")
        if not isinstance(facts, list) or not facts or not isinstance(claims, list):
            raise ValueError("beccsv_dataset_facts_or_claims_invalid")
        fact_ids = [fact.get("fact_id") for fact in facts]
        claim_ids = [claim.get("claim_id") for claim in claims]
        if (
            any(not isinstance(value, str) or not value for value in fact_ids)
            or len(set(fact_ids)) != len(fact_ids)
            or any(not isinstance(value, str) or not value for value in claim_ids)
            or len(set(claim_ids)) != len(claim_ids)
        ):
            raise ValueError("beccsv_dataset_fact_or_claim_id_invalid")
        fact_set, claim_set = set(fact_ids), set(claim_ids)
        for fact in facts:
            quote = fact.get("quote")
            if (
                not isinstance(quote, str)
                or not quote
                or quote not in transcript
                or fact.get("severity")
                not in {"critical", "high", "moderate", "informational"}
            ):
                raise ValueError("beccsv_dataset_fact_evidence_invalid")
        for claim in claims:
            references = claim.get("source_fact_ids")
            if not isinstance(references, list) or any(
                value not in fact_set for value in references
            ):
                raise ValueError("beccsv_dataset_claim_reference_invalid")
        mismatches = case.get("expected_mismatches", [])
        if not isinstance(mismatches, list):
            raise ValueError("beccsv_dataset_expected_mismatches_invalid")
        for mismatch in mismatches:
            if not isinstance(mismatch, dict) or not isinstance(
                mismatch.get("kind"), str
            ):
                raise ValueError("beccsv_dataset_expected_mismatch_invalid")
            if mismatch.get("severity") not in {
                "critical",
                "high",
                "moderate",
                "informational",
            }:
                raise ValueError("beccsv_dataset_expected_mismatch_severity_invalid")
            if (
                any(
                    isinstance(value, str) and value not in fact_set
                    for key, value in mismatch.items()
                    if key.endswith("fact_id")
                )
                or any(
                    isinstance(value, str) and value not in claim_set
                    for key, value in mismatch.items()
                    if key.endswith("claim_id")
                )
                or any(
                    not isinstance(values, list)
                    or any(value not in fact_set for value in values)
                    for key, values in mismatch.items()
                    if key.endswith("fact_ids")
                )
                or any(
                    not isinstance(values, list)
                    or any(value not in claim_set for value in values)
                    for key, values in mismatch.items()
                    if key.endswith("claim_ids")
                )
            ):
                raise ValueError("beccsv_dataset_expected_mismatch_reference_invalid")
        fact_count += len(facts)
        claim_count += len(claims)
    return {
        "dataset_id": manifest["dataset_id"],
        "case_count": len(cases),
        "source_fact_count": fact_count,
        "note_claim_count": claim_count,
        "synthetic_only": True,
        "clinical_gold": False,
    }


def lock_manifest(manifest_path, lock_path):
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    summary = validate_manifest(manifest)
    lock = {
        "schema_version": "beccsv_dataset_lock_v1",
        "dataset_id": summary["dataset_id"],
        "manifest_sha256": sha256_bytes(manifest_bytes),
        **summary,
        "acceptance_use_authorized": False,
    }
    Path(lock_path).write_text(
        json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return lock


def validate_lock(manifest_path, lock_path):
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    summary = validate_manifest(manifest)
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    if (
        lock.get("schema_version") != "beccsv_dataset_lock_v1"
        or lock.get("manifest_sha256") != sha256_bytes(manifest_bytes)
        or lock.get("acceptance_use_authorized") is not False
        or any(lock.get(key) != value for key, value in summary.items())
    ):
        raise ValueError("beccsv_dataset_lock_mismatch")
    return summary
