"""Inventory versioned report outputs and their reproducibility boundaries."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


DETERMINISTIC_OUTPUTS = [
    {
        "path": "evaluation/publications/mta-17-03-benchmark-tables-v1.json",
        "generator": "services.publication_bundle.build",
        "inputs": [
            "evaluation/datasets/primock57-expanded-v1/manifest.json",
            "evaluation/expanded-ledger.json",
            "completed frozen source reports",
        ],
        "variable_fields": [
            "/source_commit",
            "source report hashes change only when frozen inputs change",
        ],
        "rebuild_rule": "Byte-for-byte stable on the same source commit and frozen input bytes.",
    },
    {
        "path": "evaluation/supplementary/mta-17-05-sample-results-v1.json",
        "generator": "services.supplementary_bundle.build",
        "inputs": [
            "evaluation/datasets/primock57-expanded-v1/manifest.json",
            "evaluation/datasets/primock57-expanded-v1/lock.json",
            "evaluation/expanded-ledger.json",
            "completed frozen source reports",
        ],
        "variable_fields": [
            "/source_commit",
            "source report hashes change only when frozen inputs change",
        ],
        "rebuild_rule": "Byte-for-byte stable on the same source commit and frozen input bytes.",
    },
    {
        "path": "evaluation/architecture/algorithm-reference-v1.json",
        "generator": "services.algorithm_reference.build",
        "inputs": ["services/evidence_graph.py", "services/review/engine.py"],
        "variable_fields": ["/source_commit", "/source_sha256"],
        "rebuild_rule": "Byte-for-byte stable on the same source commit and source-file bytes.",
    },
    {
        "path": "evaluation/claim-provenance/10of10-provenance-v1.json",
        "generator": "services.claim_provenance.build",
        "inputs": [
            "evaluation/master-task-ledger.json",
            "each anchored source and evidence report",
        ],
        "variable_fields": [
            "/source_commit",
            "source file/report hashes change only with their inputs",
        ],
        "rebuild_rule": "Byte-for-byte stable for a fixed source commit, ledger and referenced evidence bytes.",
    },
    {
        "path": "evaluation/supply-chain/model-cards-v2.json",
        "generator": "services.supply_chain_bundle.build_bundle",
        "inputs": [
            "evaluation/model-registry.json",
            "candidate benchmark reports",
            "evaluation/candidate-access-audit.json",
        ],
        "variable_fields": ["/source_commit", "/source_hashes"],
        "rebuild_rule": "Byte-for-byte stable on the same source commit and referenced report/registry bytes.",
    },
]

VERSIONED_SNAPSHOTS = [
    {
        "path": "evaluation/supply-chain/sbom-v1.json",
        "generator": "services.supply_chain_bundle.build_bundle",
        "variable_fields": [
            "/source_commit",
            "/metadata/timestamp",
            "/components (installed Python environment snapshot)",
            "/offline_dependency_inventory",
        ],
        "versioning_rule": "Immutable versioned snapshot; byte-for-byte comparison requires the same source commit, installed Python distributions, local npm lockfile, and recorded timestamp.",
    },
    {
        "path": "evaluation/supply-chain/license-register-v1.json",
        "generator": "services.supply_chain_bundle.build_bundle",
        "variable_fields": [
            "/source_commit",
            "/python_packages (installed distribution metadata)",
        ],
        "versioning_rule": "Immutable versioned metadata snapshot; missing license declarations remain unknown.",
    },
    {
        "path": "evaluation/supply-chain/architecture-compliance-matrix-v1.json",
        "generator": "services.supply_chain_bundle.build_bundle",
        "variable_fields": ["/source_commit"],
        "versioning_rule": "Immutable source-commit-bound engineering crosswalk; not a regulatory compliance result.",
    },
    {
        "path": "evaluation/reports/mta-17-13-readiness-cli-output-v1.json",
        "generator": "python -m services.status_report",
        "variable_fields": [
            "/git_commit",
            "/offline_mode",
            "/model_availability",
            "/source_hashes",
            "/engineering",
            "/readiness_checks",
        ],
        "versioning_rule": "Immutable local environment snapshot; changes require a new report version and exact source/environment context.",
    },
    {
        "path": "evaluation/reports/mta-17-12-supply-chain-v1.json",
        "generator": "MTA-17-12 evidence receipt",
        "variable_fields": [
            "/source_commit",
            "/runtime/python",
            "/runtime/node",
            "/outputs",
        ],
        "versioning_rule": "Immutable test receipt bound to source commit, tool versions and generated artifact digests.",
    },
    {
        "path": "evaluation/reports/mta-17-13-readiness-cli-v1.json",
        "generator": "MTA-17-13 evidence receipt",
        "variable_fields": [
            "/source_commit",
            "/runtime/python",
            "/runtime/cli_output_sha256",
        ],
        "versioning_rule": "Immutable test receipt bound to source commit and captured CLI output hash.",
    },
]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(root=".", source_commit=None):
    root = Path(root).resolve()
    if source_commit is None:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    entries = []
    for policy in DETERMINISTIC_OUTPUTS + VERSIONED_SNAPSHOTS:
        path = root / policy["path"]
        if not path.is_file():
            raise ValueError(f"reproducibility_artifact_missing:{policy['path']}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"reproducibility_json_invalid:{policy['path']}") from exc
        artifact_source_commit = (
            payload.get("source_commit")
            or payload.get("git_commit")
            or (payload.get("runtime") or {}).get("source_commit")
        )
        entries.append(
            {
                **policy,
                "artifact_source_commit": artifact_source_commit,
                "artifact_sha256": _sha(path),
                "bytes": path.stat().st_size,
                "artifact_version": Path(policy["path"]).name,
            }
        )
    return {
        "schema_version": "report_reproducibility_manifest_v1",
        "source_commit": source_commit,
        "artifact_count": len(entries),
        "byte_for_byte_outputs": len(DETERMINISTIC_OUTPUTS),
        "versioned_snapshot_outputs": len(VERSIONED_SNAPSHOTS),
        "artifacts": entries,
        "policy": [
            "Never overwrite a prior benchmark or acceptance artifact; create a new versioned output path.",
            "Deterministic generators must compare equal on identical source and frozen input bytes.",
            "Runtime, environment, installed-package, source-revision, timestamp and output-digest fields are version tags when they vary by run.",
            "A field omitted from a generated artifact is not implicitly stable; record it in that generator's policy before relying on cross-run equality.",
        ],
        "limitations": [
            "This manifest covers the listed research/product report generators and snapshots, not every runtime log or transient test file in the repository.",
            "A byte-stable report does not establish correctness, clinical validity, licensing rights, or release approval.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--output", default="evaluation/reports/report-reproducibility-v1.json"
    )
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    output = Path(args.root) / args.output
    if output.exists():
        raise FileExistsError("reproducibility_manifest_versions_are_immutable")
    output.parent.mkdir(parents=True, exist_ok=True)
    value = build_manifest(args.root, args.source_commit)
    output.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({"output": str(output), "artifact_count": value["artifact_count"]})
    )


if __name__ == "__main__":
    main()
