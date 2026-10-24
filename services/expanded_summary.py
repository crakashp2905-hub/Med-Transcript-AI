"""Rebuild the expanded local comparison, preserving grouped failure-inclusive counts."""

import argparse
import json
from pathlib import Path

from services.benchmark_ranking import rank
from services.asr.profiles import content_sha256


def summarize(root="."):
    root = Path(root)
    suite = json.loads((root / "evaluation/expanded-suite-v1.json").read_text(encoding="utf-8"))
    ledger = json.loads((root / "evaluation/expanded-ledger.json").read_text(encoding="utf-8"))
    result = rank(root / suite["manifest"], root / suite["lock"], ledger["candidates"], root)
    expected = {j["candidate_id"] for j in suite["jobs"]}
    if len(suite["jobs"]) != 7 or len(expected) != 7:
        raise ValueError("Exactly seven unique predeclared local configurations are required")
    if {r["candidate_id"] for r in result["ranked"]} != expected:
        raise ValueError("All seven predeclared local configurations must have complete valid reports")
    manifest = json.loads((root / suite["manifest"]).read_text(encoding="utf-8"))
    truth = {s["sample_id"]: s for s in manifest["samples"]}
    jobs = {j["candidate_id"]: j for j in suite["jobs"]}
    source_profiles = {p["profile_id"]: p for p in json.loads((root / "evaluation/expanded-whisper-profiles.json").read_text(encoding="utf-8"))}
    models = []
    for row in result["ranked"]:
        report = json.loads((root / row["report"]).read_text(encoding="utf-8"))
        job, config = jobs[row["candidate_id"]], report["runtime_configuration"]
        if content_sha256(config) != report["profile_sha256"]:
            raise ValueError("Predeclared runtime configuration hash mismatch")
        if config["runtime_version"] != {"whisper": "1.2.1", "onnx": "0.12.0", "omi": "0.2.1"}[job["runtime"]]:
            raise ValueError("Predeclared runtime version mismatch")
        if job["runtime"] == "whisper":
            source = source_profiles[job["profile_id"]]
            if content_sha256(source) != job["source_profile_sha256"]:
                raise ValueError("Predeclared public source profile changed")
            if config.get("source_profile_sha256") != job["source_profile_sha256"] or report["profile_id"] != job["profile_id"]:
                raise ValueError("Predeclared source profile mismatch")
            if config["artifacts"] != source["artifacts"] or report["model_revision"] != source["revision"]:
                raise ValueError("Predeclared Whisper artifacts/revision mismatch")
        elif config["artifacts"] != job["expected_artifacts"] or report["model_revision"] != job["revision"]:
            raise ValueError("Predeclared artifact/revision mismatch")
        if job["runtime"] == "omi" and config.get("adapter_revision") != "reuse_capi_close_windows_dll_directories_v1":
            raise ValueError("Predeclared repaired Omi lifecycle required")
        partitions = {"by_consultation": {}, "by_role": {}, "by_day": {}}
        for sample in report["samples"]:
            reference = truth[sample["sample_id"]]
            labels = {"by_consultation": sample["group_id"], "by_role": reference["speaker_role"],
                "by_day": sample["group_id"].split("_")[0]}
            for field, label in labels.items():
                group = partitions[field].setdefault(label, {"reference_words": 0, "normalized_edits": 0, "sample_count": 0, "failed_samples": 0})
                for key in ("reference_words", "normalized_edits"):
                    group[key] += sample[key]
                group["sample_count"] += 1
                group["failed_samples"] += sample["status"] == "failed"
        for groups in partitions.values():
            for group in groups.values():
                group["normalized_wer"] = group["normalized_edits"] / group["reference_words"]
        models.append({**row, **partitions})
    return {"schema_version": "1.0", "dataset_id": result["dataset_id"], "manifest_sha256": result["manifest_sha256"],
        "sample_count": len(truth), "consultation_groups": len({s["group_id"] for s in truth.values()}),
        "reference_words": models[0]["reference_words"], "maximum_normalized_wer": result["maximum_normalized_wer"],
        "models": models, "unranked": result["unranked"], "limitations": result["limitations"],
        "clinical_release_gate": "not_evaluated", "production_model_selected": None}


def markdown(result):
    lines = ["# Expanded local ASR comparison", "",
        f"{result['sample_count']} fixed clips; {result['consultation_groups']} new consultation groups; {result['reference_words']} reference words. Required normalized WER: **≤5%**.", "",
        "All seven local configurations use text-only adapters. References, scorer, failure policy and model artifacts were fixed before inference. No paid calls.", "",
        "[Preserved Omi first attempt and Windows loader repair](expanded-omi-runtime-repair-2026-10-24.md). The final comparison uses its complete repaired rerun, not selected successful clips.", "",
        "| Rank | Model/configuration | Normalized WER | Edits / words | Failed clips | 5% gate |",
        "| --- | --- | ---: | ---: | ---: | --- |"]
    for row in result["models"]:
        lines.append(f"| {row['rank']} | {row['candidate_id']} | {row['normalized_wer']:.2%} | {row['normalized_edits']}/{row['reference_words']} | {row['failed_samples']} | {row['wer_gate']['status']} |")
    for field, title in [("by_day", "Recording days"), ("by_role", "Speaker roles"), ("by_consultation", "Consultations")]:
        lines += ["", f"## {title}", "", "| Group | Model | Edits / words | Normalized WER | Failed clips |", "| --- | --- | ---: | ---: | ---: |"]
        for row in result["models"]:
            for label, group in row[field].items():
                lines.append(f"| {label} | {row['candidate_id']} | {group['normalized_edits']}/{group['reference_words']} | {group['normalized_wer']:.2%} | {group['failed_samples']} |")
    lines += ["", result["limitations"], "", "Text-only accuracy does not establish valid clinical timestamps or safe drug/dose/unit/negation handling. Clinical adjudication remains pending. The application's active model was not changed. Concurrent CPU timings are not a capacity benchmark.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = summarize(args.root)
    path = Path(args.root) / "evaluation/reports/expanded-comparison-2026-10-24.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"sample_count": result["sample_count"], "reference_words": result["reference_words"],
        "models": [{"id": r["candidate_id"], "normalized_wer": r["normalized_wer"], "gate": r["wer_gate"]["status"]} for r in result["models"]]}))


if __name__ == "__main__":
    main()
