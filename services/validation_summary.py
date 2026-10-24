"""Summarize independently grouped follow-up recordings without changing the scorer."""

import argparse
import json
from pathlib import Path

from services.benchmark_ranking import rank


def summarize(manifest_path, lock_path, ledger_path, initial_path, root="."):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    ledger = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    ranked = rank(manifest_path, lock_path, ledger["candidates"], root)
    if ranked["unranked"]:
        raise ValueError("Validation requires complete comparable runs for every predeclared finalist")
    protocol = json.loads((Path(root) / "evaluation/validation-protocol-v1.json").read_text(encoding="utf-8"))
    profiles = [json.loads((Path(root) / r["report"]).read_text(encoding="utf-8"))["profile_id"] for r in ranked["ranked"]]
    if len(profiles) != len(protocol["model_configurations"]) or set(profiles) != set(protocol["model_configurations"]):
        raise ValueError("Validation must include exactly the predeclared model configurations")
    initial = {r["candidate_id"]: r for r in json.loads(Path(initial_path).read_text(encoding="utf-8"))["ranked"]}
    truth = {s["sample_id"]: s for s in manifest["samples"]}
    models = []
    for entry in ranked["ranked"]:
        old = initial[entry["candidate_id"]]
        if entry["profile_sha256"] != old["profile_sha256"] or entry["model_revision"] != old["model_revision"]:
            raise ValueError("Model configuration changed after initial screening")
        report = json.loads((Path(root) / entry["report"]).read_text(encoding="utf-8"))
        groups, roles = {}, {}
        for row in report["samples"]:
            for collection, label in [(groups, row["group_id"]), (roles, truth[row["sample_id"]]["speaker_role"])]:
                part = collection.setdefault(label, {"reference_words": 0, "normalized_edits": 0, "sample_count": 0, "failed_samples": 0})
                part["reference_words"] += row["reference_words"]
                part["normalized_edits"] += row["normalized_edits"]
                part["sample_count"] += 1
                part["failed_samples"] += row["status"] == "failed"
        for collection in (groups, roles):
            for part in collection.values():
                part["normalized_wer"] = part["normalized_edits"] / part["reference_words"] if part["reference_words"] else None
        models.append({**entry, "initial_screening_wer": old["normalized_wer"],
            "same_profile_as_screening": True, "by_consultation": groups, "by_role": roles})
    return {"schema_version": "1.0", "dataset_id": manifest["dataset_id"],
        "manifest_sha256": ranked["manifest_sha256"], "sample_count": len(truth),
        "consultation_groups": len({s["group_id"] for s in truth.values()}),
        "reference_words": models[0]["reference_words"], "maximum_normalized_wer": .03,
        "models": models, "production_model_selected": None, "clinical_release_gate": "not_evaluated",
        "confidence_limitations": "Only five consultation groups; speaker and training independence are unverified. No population-level confidence or clinical safety claim.",
        "decision": "No automatic production promotion; the 3% gate and independent clinical acceptance remain required."}


def markdown(summary):
    lines = ["# Follow-up validation of the two lowest-error screening configurations", "",
        f"{summary['sample_count']} clips from {summary['consultation_groups']} additional consultation groups, {summary['reference_words']} reference words.", "",
        f"Frozen manifest: `{summary['manifest_sha256']}`.", "",
        "Models, quantization and scoring were unchanged from screening. No reference edits or outcome-dependent exclusions.", "",
        "| Model/configuration | Initial 6-clip WER | New 30-clip WER | Edits / words | Failures | 3% gate |",
        "| --- | ---: | ---: | ---: | ---: | --- |"]
    for row in summary["models"]:
        lines.append(f"| {row['candidate_id']} | {row['initial_screening_wer']:.2%} | {row['normalized_wer']:.2%} | {row['normalized_edits']}/{row['reference_words']} | {row['failed_samples']} | {row['wer_gate']['status']} |")
    for field, heading in [("by_consultation", "Consultation groups"), ("by_role", "Speaker roles")]:
        lines += ["", f"## {heading}", "", "| Group | Model | Edits / words | Normalized WER |", "| --- | --- | ---: | ---: |"]
        for row in summary["models"]:
            for label, part in row[field].items():
                lines.append(f"| {label} | {row['candidate_id']} | {part['normalized_edits']}/{part['reference_words']} | {part['normalized_wer']:.2%} |")
    lines += ["", summary["confidence_limitations"], "", "These are text-only offline benchmark adapters, not clinical transcript publishers. Full consultation, microphone, noise, overlap and clinician drug/dose/unit/negation validation remains pending. The application model was not switched by these runs.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root)
    result = summarize(root / "evaluation/datasets/primock57-validation-v1/manifest.json",
        root / "evaluation/datasets/primock57-validation-v1/lock.json",
        root / "evaluation/validation-ledger.json", root / "evaluation/leaderboard.json", root)
    output = root / "evaluation/reports/follow-up-validation-2026-10-24.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"sample_count": result["sample_count"], "reference_words": result["reference_words"],
        "results": [{"model": r["candidate_id"], "normalized_wer": r["normalized_wer"], "gate": r["wer_gate"]["status"]} for r in result["models"]]}))


if __name__ == "__main__":
    main()
