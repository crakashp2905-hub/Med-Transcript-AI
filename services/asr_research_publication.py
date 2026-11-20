"""Assemble source-bound ASR research tables without running inference."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from services.publication_bundle import build as build_benchmark_publication


INPUTS = {
    "model_cards": "evaluation/reports/model-cards-v1.json",
    "negative_experiments": "evaluation/reports/negative-experiments-index-v1.json",
    "error_taxonomy": "evaluation/reports/error-taxonomy-v2/report.json",
    "matched_ablation": "evaluation/runs/meddistract-detailed-v7/matched-ablation-v3.json",
    "segmentation_ablation": "evaluation/runs/meddistract-detailed-v7/segmentation-candidates/tiny-en-vad-threshold-ablation-v1.json",
    "stratified_uncertainty": "evaluation/reports/paired-asr-stratified-bootstrap-v2.json",
    "expanded_dataset_manifest": "evaluation/datasets/primock57-expanded-v1/manifest.json",
    "detailed_dataset_manifest": "evaluation/datasets/meddistract-detailed-v1/manifest.json",
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def build(root="."):
    root = Path(root).resolve()
    sources = {}
    for name, relative in INPUTS.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"publication_input_missing_or_outside_root:{relative}")
        sources[name] = {"path": relative, "sha256": _sha(path)}

    cards = _json(root, INPUTS["model_cards"])
    negative = _json(root, INPUTS["negative_experiments"])
    taxonomy = _json(root, INPUTS["error_taxonomy"])
    matched = _json(root, INPUTS["matched_ablation"])
    segmentation = _json(root, INPUTS["segmentation_ablation"])
    uncertainty = _json(root, INPUTS["stratified_uncertainty"])

    model_table = [
        {
            "model_id": card["model_id"],
            "status": card["status"],
            "hardware": card.get("hardware"),
            "sample_count": card.get("sample_count"),
            "reference_words": card.get("reference_words"),
            "normalized_wer": card.get("normalized_wer"),
            "failed_samples": card.get("failed_samples"),
            "license_metadata": card.get("license_metadata"),
            "report": card.get("report"),
        }
        for card in cards["cards"]
    ]
    ablation_table = []
    for arm, result in matched["comparison"]["arms"].items():
        ablation_table.append({"experiment": "matched_component", "arm": arm, **result})
    for arm, result in segmentation["arms"].items():
        summary = result["summary"]
        ablation_table.append(
            {
                "experiment": "vad_threshold",
                "arm": arm,
                **summary,
                "configuration": result.get("configuration"),
            }
        )

    uncertainty_table = []
    for candidate in uncertainty["candidates"]:
        interval = candidate["overall_recording_condition_delta"]
        uncertainty_table.append(
            {
                "candidate_id": candidate["candidate_id"],
                "stratum": "recording_condition",
                "name": "distracted_minus_clean_micro_wer",
                "estimate": interval["estimate"],
                "low": interval["low"],
                "high": interval["high"],
                "groups": interval["paired_foregrounds"],
                "failed_cases_included": interval["failed_pairs_included"],
            }
        )
        for role, data in candidate["speaker_role_strata"].items():
            interval = data["paired_interval"]
            uncertainty_table.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "stratum": "reference_speaker_role",
                    "name": role,
                    "estimate": interval.get("distracted_minus_clean")
                    if interval
                    else None,
                    "low": interval.get("low") if interval else None,
                    "high": interval.get("high") if interval else None,
                    "groups": interval.get("consultation_groups") if interval else 0,
                    "failed_cases_included": data["failed_cases_included"],
                }
            )
        for term, data in candidate["literal_clinical_term_strata"].items():
            interval = data["paired_interval"]
            uncertainty_table.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "stratum": "literal_reference_term_recall",
                    "name": term,
                    "estimate": interval.get("distracted_minus_clean")
                    if interval
                    else None,
                    "low": interval.get("low") if interval else None,
                    "high": interval.get("high") if interval else None,
                    "groups": interval.get("consultation_groups")
                    if interval
                    else data["reference_bearing_consultation_groups"],
                    "failed_cases_included": data[
                        "failed_reference_bearing_cases_included"
                    ],
                }
            )

    error_table = [
        {
            "path": row["path"],
            "sha256": row["sha256"],
            "complete": row["complete"],
            "case_count": row["cases"],
        }
        for row in taxonomy["reports"]
    ]
    code_paths = sorted(
        {
            "services/asr/matched_ablation_runner.py",
            "services/asr/ablation.py",
            "services/asr/energy_vad_chunking.py",
            "services/asr/context_biasing.py",
            "services/error_taxonomy.py",
            "services/benchmark_integrity.py",
            "services/detailed_benchmark.py",
            "services/evaluation.py",
            "services/clinical_metrics.py",
            "services/canonical.py",
            "services/publication_bundle.py",
            "services/asr_research_publication.py",
        }
    )
    code_manifest = {path: _sha(root / path) for path in code_paths}
    artifact_model_digests = {}
    for card in cards["cards"]:
        artifacts = card.get("decoding", {}).get("artifacts", {})
        if artifacts:
            artifact_model_digests[card["model_id"]] = artifacts

    benchmark_publication = build_benchmark_publication(root)
    markdown = [
        "# ASR research publication tables",
        "",
        "This bundle is generated from frozen local receipts. It performs no inference.",
        "All tables are descriptive development evidence; they do not establish clinical accuracy or release eligibility.",
        "",
        "## Model cards",
        "",
        "| Model | Status | Hardware | Samples | Reference words | WER | Failed | License metadata |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in model_table:
        markdown.append(
            f"| {row['model_id']} | {row['status']} | {row['hardware']} | {row['sample_count']} | {row['reference_words']} | {row['normalized_wer']} | {row['failed_samples']} | {row['license_metadata']} |"
        )
    markdown += [
        "",
        "## Ablations",
        "",
        "| Experiment | Arm | Cases | Failed | Edits | WER | Gate |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in ablation_table:
        markdown.append(
            f"| {row['experiment']} | {row['arm']} | {row['sample_count']} | {row['failed_samples']} | {row['normalized_edits']} | {row['normalized_wer']} | {row['wer_admission']} |"
        )
    markdown += [
        "",
        "## Error receipt inventory",
        "",
        "| Source report | Cases | Complete | SHA-256 |",
        "|---|---:|---|---|",
    ]
    for row in error_table:
        markdown.append(
            f"| {row['path']} | {row['case_count']} | {row['complete']} | `{row['sha256']}` |"
        )
    markdown += [
        "",
        "## Stratified paired uncertainty",
        "",
        "| Candidate | Stratum | Name | Delta | 95% CI | Groups |",
        "|---|---|---|---:|---|---:|",
    ]
    for row in uncertainty_table:
        markdown.append(
            f"| {row['candidate_id']} | {row['stratum']} | {row['name']} | {row['estimate']} | [{row['low']}, {row['high']}] | {row['groups']} |"
        )
    markdown.append("")

    return {
        "schema_version": "asr_research_publication_bundle_v1",
        "task_id": "MTA-ASR-I09",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "sources": sources,
        "code_manifest": code_manifest,
        "model_artifact_digests": artifact_model_digests,
        "model_cards": model_table,
        "benchmark_publication": benchmark_publication,
        "ablation_table": ablation_table,
        "error_receipt_table": error_table,
        "negative_experiments": {
            "source_commit": negative["source_commit"],
            "inventory_scope": negative["inventory_scope"],
            "entry_count": len(negative["entries"]),
            "original_reports_modified": negative["original_reports_modified"],
            "independent_clinical_gold": negative["independent_clinical_gold"],
            "real_patient_release_authorized": negative[
                "real_patient_release_authorized"
            ],
        },
        "stratified_uncertainty_table": uncertainty_table,
        "generated_markdown": "\n".join(markdown),
        "inference_performed": False,
        "maximum_normalized_wer": 0.05,
        "all_admission_failures_retained": all(
            row["wer_admission"] == "fail" for row in ablation_table
        )
        and all(
            row["normalized_wer"] > 0.05
            for row in model_table
            if row["normalized_wer"] is not None
        ),
        "clinical_acceptance": False,
        "limitations": [
            "The bundles cover selected frozen experiments, not every ASR experiment ever conducted; historical negative index scope is bounded.",
            "All cited development references are not independent clinician-adjudicated gold.",
            "Term strata measure literal reference occurrence recall, not clinical concept correctness; sparse groups have null intervals.",
            "Some older model-card license metadata is null and must remain unknown.",
            "The unchanged 5% WER admission gate fails all included model and ablation rows; no model is promoted.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    bundle = build(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(bundle["generated_markdown"], encoding="utf-8")
    print(json.dumps({"output": output.as_posix(), "status": "written"}))


if __name__ == "__main__":
    main()
