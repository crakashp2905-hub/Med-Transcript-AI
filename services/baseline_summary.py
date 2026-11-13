"""Scope-separated historical baselines; no inference, retuning or universal WER."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from services.engineering_status import sha256


SOURCES = {
    "short": "evaluation/reports/expanded-comparison-2026-10-24.json",
    "long": "evaluation/reports/conversation-ablation-resumed-2026-10-26.json",
    "paired": "evaluation/reports/detailed-campaign-execution-receipt-2026-10-29.json",
    "draft": "evaluation/reports/detailed-drafting-summary-2026-10-29.json",
}


def summarize(root="."):
    root = Path(root)
    frozen = json.loads(
        (root / "evaluation/reports/engineering-baseline.json").read_text(
            encoding="utf-8"
        )
    )["benchmark_sha256"]
    documents = {}
    for key, name in SOURCES.items():
        if sha256(root / name) != frozen[name]:
            raise ValueError("historical_baseline_source_changed")
        documents[key] = json.loads((root / name).read_text(encoding="utf-8"))
    short = next(
        row
        for row in documents["short"]["models"]
        if row["candidate_id"] == "omi-med-stt-v1"
    )
    long = documents["long"]["baseline_mixed_fixed30"]
    paired = next(
        row
        for row in documents["paired"]["completed_conditions"]
        if row["candidate"] == "omi-med-stt-v1-native-empty" and row["mode"] == "fixed"
    )

    def metric(row):
        edits, words = row["normalized_edits"], row["reference_words"]
        if type(edits) is not int or type(words) is not int or edits < 0 or words <= 0:
            raise ValueError("invalid_baseline_denominator")
        if abs(row["normalized_wer"] - edits / words) > 1e-12:
            raise ValueError("baseline_arithmetic_mismatch")
        return {
            "normalized_edits": edits,
            "reference_words": words,
            "normalized_wer": edits / words,
            "maximum_normalized_wer": 0.05,
            "five_percent_gate": "fail" if edits * 20 > words else "pass",
        }

    scopes = [
        {
            "scope": "118_selected_short_clips",
            "consultation_groups": 20,
            "candidate": "omi-med-stt-v1",
            **metric(short),
        },
        {
            "scope": "three_full_mock_consultations",
            "consultation_groups": 3,
            "candidate": "omi-med-stt-v1",
            **metric(long),
        },
        {
            "scope": "meddistract_eight_foregrounds_clean",
            "consultation_groups": 8,
            "candidate": "omi-med-stt-v1-native-empty",
            **metric(paired["clean"]),
        },
        {
            "scope": "meddistract_same_eight_foregrounds_distracted",
            "consultation_groups": 8,
            "candidate": "omi-med-stt-v1-native-empty",
            **metric(paired["distracted"]),
        },
    ]
    if any(sha256(root / name) != frozen[name] for name in SOURCES.values()):
        raise ValueError("baseline_source_changed_during_summary")
    draft_rows = []
    for row in documents["draft"]["rows"]:
        attempted = row["attempted_cases"]
        exact = row["exact_preservation_cases"]
        failed = row["failed_cases"]
        if (
            type(attempted) is not int
            or type(exact) is not int
            or type(failed) is not int
            or attempted < 0
            or exact < 0
            or failed < 0
            or exact + failed > attempted
        ):
            raise ValueError("invalid_failure_inclusive_draft_counts")
        draft_rows.append(
            {
                **row,
                "metric": "synthetic_source_fact_preservation",
                "failure_inclusive_case_count": attempted,
                "non_exact_cases": attempted - exact,
                "incorrect_nonfailed_cases": attempted - exact - failed,
                "clinical_accuracy": "not_measured",
                "clinical_accuracy_reason": "independent_clinical_gold_unavailable",
            }
        )
    return {
        "schema_version": "scope_separated_baselines_v1",
        "scopes": scopes,
        "draft_preservation": draft_rows,
        "source_sha256": {name: frozen[name] for name in SOURCES.values()},
        "code_sha256": sha256(Path(__file__)),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "universal_combined_wer": None,
        "inference_calls": 0,
        "automatic_model_promotion": False,
        "independent_clinical_gold": False,
        "clinical_release": False,
        "limitations": [
            "Selected clips, three whole consultations and paired clean/distracted inputs are different evaluation scopes.",
            "Clean/distracted variants are the same foreground subjects, not 16 independent consultations.",
            "Native-empty reconstruction remains explicitly distinguished from the original Omi wrapper and failures.",
            "Source-note preservation is not clinical note accuracy, human correction time or independent adjudication.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with Path(args.out).open("x", encoding="utf-8") as target:
        json.dump(summarize(), target, indent=2)
