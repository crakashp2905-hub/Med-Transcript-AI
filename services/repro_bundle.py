"""Build a model-free reproducibility manifest from committed artifacts."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
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
                "dataset_id": json.loads(manifest.read_text(encoding="utf-8")).get(
                    "dataset_id"
                ),
                "source_revision": json.loads(manifest.read_text(encoding="utf-8")).get(
                    "source_revision"
                ),
                "license": (
                    json.loads(manifest.read_text(encoding="utf-8")).get("license")
                    or json.loads(manifest.read_text(encoding="utf-8")).get(
                        "license_id"
                    )
                ),
                "data_class": json.loads(manifest.read_text(encoding="utf-8")).get(
                    "data_class"
                ),
                "split": json.loads(manifest.read_text(encoding="utf-8")).get(
                    "split_role"
                )
                or json.loads(manifest.read_text(encoding="utf-8")).get("split"),
                "case_count": len(
                    json.loads(manifest.read_text(encoding="utf-8")).get("cases", [])
                ),
                "license_status": "declared_in_manifest"
                if json.loads(manifest.read_text(encoding="utf-8")).get("license")
                or json.loads(manifest.read_text(encoding="utf-8")).get("license_id")
                else "not_declared_in_manifest",
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
    model_candidates = []
    for candidate in ledger_body.get("candidates", []):
        item = {
            "candidate_id": candidate.get("candidate_id"),
            "status": candidate.get("status"),
            "reason": candidate.get("reason"),
            "runtime_variant": candidate.get("runtime_variant"),
            "report": candidate.get("report"),
            "model_revision": None,
            "profile_id": None,
            "profile_sha256": None,
            "model_artifact_digests": {},
            "model_digest_status": "unavailable_candidate_not_run",
        }
        report_name = candidate.get("report")
        if candidate.get("status") == "completed" and isinstance(report_name, str):
            report_path = (root / report_name).resolve()
            if not report_path.is_relative_to(root) or not report_path.is_file():
                raise ValueError("reproducibility_model_report_missing_or_outside_root")
            result = json.loads(report_path.read_text(encoding="utf-8"))
            runtime_config = result.get("runtime_configuration") or {}
            digests = (
                runtime_config.get("artifacts")
                or result.get("model_artifact_digests")
                or {}
            )
            item.update(
                {
                    "report_sha256": hashlib.sha256(
                        report_path.read_bytes()
                    ).hexdigest(),
                    "model_revision": result.get("model_revision")
                    or runtime_config.get("revision"),
                    "profile_id": result.get("profile_id")
                    or runtime_config.get("profile_id"),
                    "profile_sha256": result.get("profile_sha256"),
                    "model_artifact_digests": digests,
                    "model_digest_status": "artifact_digests_recorded"
                    if digests
                    else "model_artifact_digest_not_in_report",
                }
            )
        model_candidates.append(item)
    script_names = [
        "services/repro_bundle.py",
        "services/offline_acceptance.py",
        "services/engineering_status.py",
        "services/benchmark_ranking.py",
        "tests/test_repro_bundle.py",
        "tests/test_benchmark_ranking.py",
    ]
    scripts = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in script_names
        if (root / name).is_file()
    }
    packages = {}
    for name in ("fastapi", "pydantic", "uvicorn", "pytest", "ruff"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "schema_version": "repro_bundle_v2",
        "source_commit": source_commit,
        "worktree_clean": not git_status,
        "uncommitted_path_count": len(git_status),
        "datasets": datasets,
        "model_candidates": model_candidates,
        "scripts": scripts,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "packages": packages,
            "pyproject_sha256": hashlib.sha256(
                (root / "pyproject.toml").read_bytes()
            ).hexdigest(),
            "constraints_sha256": hashlib.sha256(
                (root / "constraints-ci.txt").read_bytes()
            ).hexdigest(),
        },
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
