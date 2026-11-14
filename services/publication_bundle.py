"""Render publication tables from frozen benchmark reports without inference."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from services.expanded_summary import markdown, summarize


def build(root="."):
    root = Path(root).resolve()
    summary = summarize(root)
    manifest_path = root / "evaluation/datasets/primock57-expanded-v1/manifest.json"
    ledger_path = root / "evaluation/expanded-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    report_sources = []
    for candidate in ledger["candidates"]:
        path = candidate.get("report")
        if candidate.get("status") != "completed" or not path:
            continue
        source = (root / path).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError("publication_source_report_missing_or_outside_root")
        report_sources.append(
            {
                "candidate_id": candidate["candidate_id"],
                "path": path,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    table = markdown(summary)
    if len(report_sources) != len(summary["models"]):
        raise ValueError("publication_report_count_does_not_match_ranked_models")
    if any(row["failed_samples"] < 0 for row in summary["models"]):
        raise ValueError("invalid_failure_count")
    return {
        "schema_version": "frozen_benchmark_publication_v1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "dataset": {
            "path": "evaluation/datasets/primock57-expanded-v1/manifest.json",
            "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "dataset_id": summary["dataset_id"],
            "sample_count": summary["sample_count"],
            "reference_words": summary["reference_words"],
        },
        "source_reports": report_sources,
        "report": summary,
        "generated_markdown": table,
        "negative_results_preserved": True,
        "clinical_release_gate": "not_evaluated",
        "production_model_selected": None,
        "inference_performed": False,
        "limitations": [
            "Tables are regenerated from frozen development benchmark reports; no new model inference is performed.",
            "All seven candidates use text-only adapters; WER does not establish valid application timestamps or clinical safety.",
            "The 5% gate remains unchanged and candidate failures are retained.",
            "Clinical adjudication remains pending and no production model is selected.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="evaluation/publications/mta-17-03-benchmark-tables-v1.json",
    )
    args = parser.parse_args()
    output = Path(args.output)
    bundle = build(".")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(bundle, stream, indent=2)
        stream.write("\n")
    output.with_suffix(".md").write_text(
        bundle["generated_markdown"], encoding="utf-8", newline="\n"
    )
    print(json.dumps({"output": output.as_posix(), "status": "written"}))


if __name__ == "__main__":
    main()
