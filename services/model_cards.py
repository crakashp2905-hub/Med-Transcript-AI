"""Generate report-only model cards from committed registry and benchmark JSON."""

import json
from pathlib import Path
from services.clinical_limitations import CLINICAL_LIMITATIONS


def generate(root="."):
    root = Path(root).resolve()
    registry = json.loads(
        (root / "evaluation/model-registry.json").read_text(encoding="utf-8")
    )
    cards = []
    for candidate in registry.get("candidates", []):
        report_path = candidate.get("expanded_comparison", {}).get(
            "report"
        ) or candidate.get("report")
        report = None
        if report_path and (root / report_path).is_file():
            report = json.loads((root / report_path).read_text(encoding="utf-8"))
        runtime = (report or {}).get("runtime_configuration", {})
        samples = (report or {}).get("samples", [])
        role_metrics = {}
        for sample in samples:
            role = (
                "patient"
                if "_patient." in sample.get("sample_id", "")
                else (
                    "doctor" if "_doctor." in sample.get("sample_id", "") else "unknown"
                )
            )
            row = role_metrics.setdefault(
                role, {"reference_words": 0, "normalized_edits": 0, "failed_samples": 0}
            )
            row["reference_words"] += sample.get("reference_words", 0) or 0
            row["normalized_edits"] += sample.get("normalized_edits", 0) or 0
            row["failed_samples"] += int(sample.get("status") != "completed")
        for row in role_metrics.values():
            row["normalized_wer"] = (
                (row["normalized_edits"] / row["reference_words"])
                if row["reference_words"]
                else None
            )
        cards.append(
            {
                "model_id": candidate.get("id"),
                "language": "English",
                "status": candidate.get("status"),
                "license_metadata": candidate.get("license_metadata"),
                "report": report_path,
                "report_available": report is not None,
                "hardware": runtime.get("device"),
                "decoding": runtime,
                "sample_count": (report or {}).get("sample_count"),
                "reference_words": (report or {}).get("reference_words"),
                "normalized_wer": (report or {}).get("normalized_wer"),
                "failed_samples": (report or {}).get("failed_samples"),
                "timeouts": sum(
                    1
                    for s in samples
                    if s.get("error_code") in ("timeout", "timed_out")
                ),
                "role_metrics": role_metrics,
                "limitations": [
                    *CLINICAL_LIMITATIONS,
                    "Missing reports and blocked candidates remain visible.",
                    "No candidate is promoted unless the immutable 5% gate is met.",
                ],
            }
        )
    return {
        "schema_version": "model_cards_v1",
        "cards": cards,
        "maximum_normalized_wer": 0.05,
        "clinical_release_gate": "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        "real_patient_release_authorized": False,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    Path(args.out).write_text(json.dumps(generate(), indent=2) + "\n", encoding="utf-8")
