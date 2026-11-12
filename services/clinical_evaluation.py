"""Reproducible development evaluation; never manufactures clinical gold labels."""

import argparse
import hashlib
import json
from pathlib import Path

from services.clinical_metrics import evaluate
from services.review.clinical import check_claim


def adversarial(path, *, include_relationships=True):
    raw = Path(path).read_bytes()
    fixture = json.loads(raw)
    rows = []
    counts = dict(true_positive=0, false_positive=0, true_negative=0, false_negative=0)
    for case in fixture["cases"]:
        findings = check_claim(
            case["source"], case["claim"], include_relationships=include_relationships
        )
        unsafe, expected = bool(findings), case["expected_unsafe"]
        key = ("true_" if unsafe == expected else "false_") + (
            "positive" if unsafe else "negative"
        )
        counts[key] += 1
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected_unsafe": expected,
                "detected_unsafe": unsafe,
                "findings": [x["code"] for x in findings],
            }
        )
    return {
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "scope": fixture["annotation_status"],
        "validator": "independent_clinical_rules_v2+explicit_relationships_v1"
        if include_relationships
        else "independent_clinical_rules_v2",
        "limitation": "Small synthetic developer fixture; not an estimate of clinical sensitivity or specificity.",
        "confusion_matrix": counts,
        "cases": rows,
    }


def annotated(path):
    raw = Path(path).read_bytes()
    source = json.loads(raw)
    cases = source.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("annotated_cases_required")
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "evaluation"
        / "clinical-asr-secondary-endpoints-v1.json"
    )
    return {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "secondary_endpoint_registry_sha256": hashlib.sha256(
            policy_path.read_bytes()
        ).hexdigest(),
        "cases": [
            {
                "id": case["id"],
                **evaluate(
                    case["reference"],
                    case["hypothesis"],
                    case["expected"],
                    case["observed"],
                    case.get("failed", False),
                    impact_weights=case.get("impact_weights"),
                ),
            }
            for case in cases
        ],
        "limitation": "Annotation quality and impact weights require independent clinical review; automated metrics do not establish clinical validity.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adversarial")
    parser.add_argument(
        "--annotated",
        help="JSON cases: reference, hypothesis, expected and observed independent concept annotations, failed",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if bool(args.adversarial) == bool(args.annotated):
        parser.error("Choose exactly one evaluation source")
    if args.adversarial:
        report = adversarial(args.adversarial)
    else:
        report = annotated(args.annotated)
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "evaluation"
        / "clinical-asr-secondary-endpoints-v1.json"
    )
    report["secondary_endpoint_registry_sha256"] = hashlib.sha256(
        policy_path.read_bytes()
    ).hexdigest()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as destination:
        destination.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
