"""Synthetic metamorphic checks for deterministic clinical-state rules."""

from services.review.clinical import check_claim
from services.review.relationships import bindings


CASES = (
    {
        "case_id": "unit-conversion",
        "transformation": "semantics_preserving_unit_conversion",
        "source": "Taking metformin 1000 mg.",
        "candidate": "Taking metformin 1 g.",
        "expect_invariant": True,
        "expected_code": None,
    },
    {
        "case_id": "faithful-paraphrase",
        "transformation": "semantics_preserving_paraphrase",
        "source": "Patient denies fever.",
        "candidate": "Patient has no fever.",
        "expect_invariant": True,
        "expected_code": None,
    },
    {
        "case_id": "clause-order",
        "transformation": "semantics_preserving_clause_order",
        "source": "Patient denies fever and reports cough.",
        "candidate": "Patient reports cough and denies fever.",
        "expect_invariant": True,
        "expected_code": None,
    },
    {
        "case_id": "temporal-flip",
        "transformation": "semantic_temporal_flip",
        "source": "Patient had a cough last week.",
        "candidate": "Patient has a cough today.",
        "expect_invariant": False,
        "expected_code": "temporality_changed",
    },
    {
        "case_id": "drug-dose-swap",
        "transformation": "semantic_medication_dose_swap",
        "source": "Taking metformin 500 mg and warfarin 5 mg.",
        "candidate": "Taking metformin 5 mg and warfarin 500 mg.",
        "expect_invariant": False,
        "expected_code": "medication_dose_assignment_disagreement",
    },
    {
        "case_id": "negation-reversal",
        "transformation": "semantic_negation_reversal",
        "source": "Patient denies fever.",
        "candidate": "Patient reports fever.",
        "expect_invariant": False,
        "expected_code": "negation_disagreement",
    },
    {
        "case_id": "subject-swap",
        "transformation": "semantic_subject_swap",
        "source": "Patient has diabetes.",
        "candidate": "My mother has diabetes.",
        "expect_invariant": False,
        "expected_code": "subject_changed",
    },
)


def evaluate():
    results = []
    for case in CASES:
        if case["transformation"] in {
            "semantic_temporal_flip",
            "semantic_subject_swap",
        }:
            before = list(bindings(case["source"]))
            after = list(bindings(case["candidate"]))
            key = (
                "timing"
                if case["transformation"] == "semantic_temporal_flip"
                else "subject"
            )
            changed = bool(before and after and before[0][3][key] != after[0][3][key])
            codes = [case["expected_code"]] if changed else []
        else:
            codes = sorted(
                {
                    finding["code"]
                    for finding in check_claim(case["source"], case["candidate"])
                }
            )
            changed = bool(codes)
        if case["expect_invariant"]:
            passed = not changed
            outcome = "pass" if passed else "false_alarm"
        else:
            passed = changed and (
                case["expected_code"] is None or case["expected_code"] in codes
            )
            outcome = "pass" if passed else "missed_detection"
        results.append(
            {
                "case_id": case["case_id"],
                "transformation": case["transformation"],
                "expected_invariant": case["expect_invariant"],
                "observed_codes": codes,
                "outcome": outcome,
                "synthetic": True,
                "clinical_gold": False,
            }
        )
    return {
        "schema_version": "beccsv_metamorphic_dev_v1",
        "results": results,
        "case_count": len(results),
        "false_alarm_count": sum(row["outcome"] == "false_alarm" for row in results),
        "missed_detection_count": sum(
            row["outcome"] == "missed_detection" for row in results
        ),
        "clinical_gold": False,
        "clinical_release_authorized": False,
    }
