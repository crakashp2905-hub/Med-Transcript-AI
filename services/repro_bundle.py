"""Build a model-free reproducibility manifest from committed artifacts."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def build(root="."):
    root = Path(root).resolve()
    names = [
        "pyproject.toml",
        "constraints-ci.txt",
        "evaluation/reports/engineering-baseline.json",
        "evaluation/reports/engineering-task-status.json",
        "docs/demo-runbook-offline.md",
        "evaluation/master-task-ledger.json",
        "evaluation/benchmark-ledger.json",
        "evaluation/detailed-suite-v7.json",
        "evaluation/leaderboard-eval-v2.json",
    ]
    artifacts = []
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError("reproducibility_artifact_missing")
        artifacts.append(
            {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    benchmark_ledger = root / "evaluation/benchmark-ledger.json"
    ledger_body = json.loads(benchmark_ledger.read_text(encoding="utf-8"))
    recorded = {item["path"] for item in artifacts}
    for candidate in ledger_body.get("candidates", []):
        report_name = candidate.get("report")
        if candidate.get("status") != "completed" or not isinstance(report_name, str):
            continue
        report_path = (root / report_name).resolve()
        if not report_path.is_relative_to(root) or not report_path.is_file():
            raise ValueError("reproducibility_benchmark_report_missing_or_outside_root")
        if report_name not in recorded:
            artifacts.append(
                {
                    "path": report_name,
                    "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                }
            )
            recorded.add(report_name)
    dataset_names = [
        "evaluation/datasets/primock57-smoke-v1/manifest.json",
        "evaluation/datasets/primock57-expanded-v1/manifest.json",
        "evaluation/datasets/primock57-validation-v1/manifest.json",
        "evaluation/datasets/primock57-full-v1/manifest.json",
        "evaluation/datasets/primock57-full-expansion-v1/manifest.json",
        "evaluation/datasets/meddistract-detailed-v1/manifest.json",
        "evaluation/datasets/beccsv-synthetic-dev-v1/manifest.json",
    ]
    datasets = []
    for name in dataset_names:
        manifest = root / name
        if not manifest.is_file():
            continue
        lock = manifest.parent / "lock.json"
        datasets.append(
            {
                "manifest": name,
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "lock": lock.relative_to(root).as_posix() if lock.is_file() else None,
                "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()
                if lock.is_file()
                else None,
            }
        )
    code_names = [
        "services/evaluation.py",
        "services/evaluation_envelope.py",
        "services/evaluation_metrics.py",
        "services/asr/subgroup_metrics.py",
        "services/asr/pareto.py",
        "services/benchmark_ranking.py",
    ]
    source_code = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in code_names
    }
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    git_status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=root, text=True
    ).splitlines()
    return {
        "schema_version": "repro_bundle_v1",
        "source_commit": source_commit,
        "worktree_clean": not git_status,
        "uncommitted_path_count": len(git_status),
        "datasets": datasets,
        "source_code_sha256": source_code,
        "commands": [
            "python -m pytest -q tests/test_evaluation.py tests/test_evaluation_envelope.py tests/test_evaluation_metrics.py tests/test_asr_subgroup_metrics.py tests/test_benchmark_ranking.py",
            "python -m services.offline_acceptance",
            "python -m services.engineering_status",
            "python -m services.benchmark_ranking --out evaluation/leaderboard-refresh-vN.json --supersedes evaluation/leaderboard-eval-v2.json",
            "python -m services.repro_bundle --output evaluation/reproducibility-pack-vN.json",
        ],
        "artifacts": artifacts,
        "negative_results_preserved": True,
        "model_free": True,
        "downloads_attempted": 0,
        "paid_calls": 0,
        "clinical_release": "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        "real_patient_release_authorized": False,
        "limitations": [
            "Benchmark manifests and report hashes reproduce development evidence only.",
            "No independent clinical annotation cohort, qualified human study, or safety validation is included.",
            "Missing, gated, paid and resource-blocked model results remain unavailable and are not imputed.",
            "Worktree changes are reported by count; this bundle hashes only the listed committed and tracked artifacts.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="evaluation/reproducibility-pack-v1.json")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(build("."), stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": output.as_posix(), "status": "written"}))


if __name__ == "__main__":
    main()
