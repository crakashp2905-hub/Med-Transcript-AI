"""Assemble local-only software, model, license, and control inventories."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tomllib
from urllib.parse import quote

from services.model_cards import generate as generate_model_cards
from services.offline_sbom import build_sbom


CONTROL_ROWS = [
    {
        "control": "Version-bound clinician approval and no automatic signing",
        "state": "prototype_control_tested",
        "implementation": [
            "services/review/routers/approvals.py",
            "services/review/presentation.py",
        ],
        "tests": ["tests/test_presentation_tools.py", "tests/test_review_workflow.py"],
        "limitation": "Synthetic workflow tests do not establish clinical authorization or identity assurance.",
    },
    {
        "control": "Evidence graph and source integrity checks",
        "state": "prototype_control_tested",
        "implementation": ["services/evidence_graph.py", "services/review/engine.py"],
        "tests": ["tests/test_evidence_graph.py", "tests/test_review_workflow.py"],
        "limitation": "Test coverage does not establish clinical correctness of source statements.",
    },
    {
        "control": "Authentication, authorization, and encounter access boundaries",
        "state": "prototype_control_tested",
        "implementation": [
            "services/review/service.py",
            "services/review/routers/workspace.py",
        ],
        "tests": ["tests/test_foundation.py", "tests/test_offline_onboarding.py"],
        "limitation": "Institution identity provider, deployment configuration, and production access review are not approved.",
    },
    {
        "control": "Audit events and tamper detection",
        "state": "prototype_control_tested",
        "implementation": [
            "services/audit_integrity.py",
            "services/review/routers/exports.py",
        ],
        "tests": ["tests/test_audit_integrity.py", "tests/test_presentation_tools.py"],
        "limitation": "Production log retention, monitoring, key custody, and incident operations are unvalidated.",
    },
    {
        "control": "Offline mode and explicit provider boundaries",
        "state": "prototype_control_tested",
        "implementation": [
            "services/offline_demo.py",
            "services/offline_acceptance.py",
        ],
        "tests": [
            "tests/test_offline_engineering.py",
            "tests/test_offline_onboarding.py",
        ],
        "limitation": "A local synthetic test does not certify a deployed host's network isolation.",
    },
    {
        "control": "Retention, backup, and recovery paths",
        "state": "prototype_control_tested",
        "implementation": ["services/maintenance.py", "services/encrypted_backup.py"],
        "tests": ["tests/test_maintenance.py", "tests/test_retention_coverage.py"],
        "limitation": "Institutional retention policy and real key custody remain unapproved.",
    },
    {
        "control": "Clinical quality, independent verification, and human review",
        "state": "external_evidence_blocked",
        "implementation": [
            "services/clinical_limitations.py",
            "services/review/engine.py",
        ],
        "tests": [
            "tests/test_clinical_limitations.py",
            "tests/test_publication_bundle.py",
        ],
        "limitation": "Independent clinical annotations and qualified reviewers are unavailable; the ASR gate remains unmet.",
    },
    {
        "control": "Receiver-specific FHIR profile and EHR transaction",
        "state": "external_integration_blocked",
        "implementation": [
            "services/review/presentation.py",
            "services/review/routers/exports.py",
        ],
        "tests": ["tests/test_presentation_tools.py"],
        "limitation": "No external FHIR validator, receiver profile, EHR sandbox, transaction, or certification was used.",
    },
    {
        "control": "Model and dependency license review",
        "state": "metadata_inventory_only_review_required",
        "implementation": [
            "evaluation/model-registry.json",
            "pyproject.toml",
            "apps/clinician-web/package-lock.json",
        ],
        "tests": ["tests/test_model_cards.py", "tests/test_offline_sbom.py"],
        "limitation": "Metadata collection is not a legal terms review; missing declarations remain unknown.",
    },
]

# Exact candidate-to-repository links recorded in candidate-access-audit.json.
# Unmapped candidates remain unknown rather than inheriting another model's terms.
MODEL_AUDIT_REPOS = {
    "google-medasr-greedy": "google/medasr",
    "google-medasr-approved-decoder": "google/medasr",
    "eka-parrotlet-a-en-5b": "ekacare/parrotlet-a-en-5b",
    "eka-parrotlet-a-2.5-pro-english": "ekacare/parrotlet-a-2.5-pro",
    "omi-med-stt-v1": "omi-health/omi-med-stt-v1-gguf",
    "multimed-whisper-small-english": "leduckhai/MultiMed-ST",
    "distil-whisper-large-v3": "Systran/faster-distil-whisper-large-v3",
    "parakeet-tdt-0.6b-v2": "nvidia/parakeet-tdt-0.6b-v2",
    "canary-qwen-2.5b": "nvidia/canary-qwen-2.5b",
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _purl_ecosystem(name, version, ecosystem):
    package_name = quote(name, safe="/")
    return f"pkg:{ecosystem}/{package_name}@{version}"


def _node_components(lock):
    components = []
    packages = lock.get("packages", {})
    for key, item in sorted(packages.items()):
        if not key or not key.startswith("node_modules/") or not item.get("version"):
            continue
        name = item.get("name") or key.split("node_modules/")[-1]
        version = str(item["version"])
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "bom-ref": _purl_ecosystem(name, version, "npm"),
                "purl": _purl_ecosystem(name, version, "npm"),
                "scope": "optional" if item.get("dev") else "required",
                "dependency_class": "locked_npm_dependency",
                "inventory_status": "lockfile_entry",
            }
        )
    return components


def _license_register(root, source_commit, sbom, node_lock):
    python_packages = []
    direct_required = set()
    direct_optional = set()
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    from services.offline_sbom import requirement_names

    direct_required, direct_optional = requirement_names(pyproject)
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        expression = dist.metadata.get("License-Expression")
        legacy = dist.metadata.get("License")
        classifiers = [
            item.removeprefix("License :: ")
            for item in dist.metadata.get_all("Classifier", [])
            if item.startswith("License :: ")
        ]
        normalized = name.lower().replace("_", "-").replace(".", "-")
        python_packages.append(
            {
                "name": name,
                "version": dist.version,
                "ecosystem": "pypi",
                "license_expression": expression,
                "legacy_license_text": legacy,
                "license_classifiers": classifiers,
                "license_status": "metadata_declared"
                if expression or legacy or classifiers
                else "unknown",
                "dependency_role": "direct_required"
                if normalized in direct_required
                else "direct_optional"
                if normalized in direct_optional
                else "installed_transitive_or_tooling",
            }
        )
    node_packages = []
    for key, item in sorted(node_lock.get("packages", {}).items()):
        if not key.startswith("node_modules/") or not item.get("version"):
            continue
        name = item.get("name") or key.split("node_modules/")[-1]
        node_packages.append(
            {
                "name": name,
                "version": str(item["version"]),
                "ecosystem": "npm",
                "license_expression": item.get("license"),
                "license_status": "metadata_declared"
                if item.get("license")
                else "unknown",
                "dependency_role": "development" if item.get("dev") else "runtime",
            }
        )

    registry = json.loads(
        (root / "evaluation/model-registry.json").read_text(encoding="utf-8")
    )
    access_audit = json.loads(
        (root / "evaluation/candidate-access-audit.json").read_text(encoding="utf-8")
    )
    audited_repos = {item["repo"]: item for item in access_audit.get("candidates", [])}
    models = []
    for model in registry.get("candidates", []):
        repo = MODEL_AUDIT_REPOS.get(model.get("id"))
        audited = audited_repos.get(repo)
        metadata = model.get("license_metadata") or (
            audited.get("license_metadata") if audited else None
        )
        models.append(
            {
                "id": model.get("id"),
                "license_metadata": metadata,
                "license_source": "model_registry"
                if model.get("license_metadata")
                else "candidate_access_audit_exact_repo_match"
                if audited
                else "unknown",
                "license_status": "metadata_declared_review_required"
                if metadata and metadata != "other"
                else "unclear_metadata_review_required"
                if metadata
                else "unknown",
                "repository": repo,
                "access_status": model.get("status"),
                "weight_distributed_in_repository": False,
                "clinical_or_commercial_rights_concluded": False,
            }
        )

    datasets = []
    data_root = root / "evaluation/datasets"
    for dataset_dir in sorted(p for p in data_root.iterdir() if p.is_dir()):
        notices = sorted(
            p
            for p in dataset_dir.iterdir()
            if p.is_file() and p.name.lower().startswith("license")
        )
        datasets.append(
            {
                "dataset_id": dataset_dir.name,
                "license_files": [
                    {"path": p.relative_to(root).as_posix(), "sha256": _sha(p)}
                    for p in notices
                ],
                "license_status": "notice_present_review_required"
                if notices
                else "unknown_no_local_license_notice",
                "rights_concluded": False,
            }
        )
    return {
        "schema_version": "license_register_v1",
        "source_commit": source_commit,
        "scope": "Local manifest and installed-metadata inventory; not legal advice or a license compatibility opinion.",
        "python_packages": sorted(
            python_packages, key=lambda x: (x["name"].lower(), x["version"])
        ),
        "npm_packages": node_packages,
        "models": models,
        "datasets": datasets,
        "summary": {
            "python_packages": len(python_packages),
            "python_unknown_license": sum(
                x["license_status"] == "unknown" for x in python_packages
            ),
            "npm_packages": len(node_packages),
            "npm_unknown_license": sum(
                x["license_status"] == "unknown" for x in node_packages
            ),
            "models": len(models),
            "models_with_unknown_license": sum(
                x["license_status"] == "unknown" for x in models
            ),
            "datasets": len(datasets),
            "datasets_without_local_notice": sum(
                not x["license_files"] for x in datasets
            ),
        },
        "inputs": {
            "sbom_component_inventory_sha256": next(
                prop["value"]
                for prop in sbom["metadata"]["properties"]
                if prop["name"] == "packageInventorySha256"
            ),
            "python_constraints_sha256": _sha(root / "constraints-ci.txt"),
            "pyproject_sha256": _sha(root / "pyproject.toml"),
            "npm_lock_sha256": _sha(root / "apps/clinician-web/package-lock.json"),
            "model_registry_sha256": _sha(root / "evaluation/model-registry.json"),
            "candidate_access_audit_sha256": _sha(
                root / "evaluation/candidate-access-audit.json"
            ),
        },
    }


def _architecture_matrix(root, source_commit):
    rows = []
    for control in CONTROL_ROWS:
        for path in control["implementation"] + control["tests"]:
            if not (root / path).is_file():
                raise ValueError(f"architecture_matrix_reference_missing:{path}")
        rows.append(control)
    return {
        "schema_version": "internal_architecture_control_matrix_v1",
        "source_commit": source_commit,
        "frameworks": [],
        "regulatory_conformance_claim": False,
        "scope": "Internal architecture and evidence crosswalk only; no regulatory, security certification, clinical safety, or interoperability compliance conclusion.",
        "controls": rows,
        "open_gates": [
            "independent_clinical_review",
            "institutional_security_and_privacy_approval",
            "receiver_specific_ehr_validation",
        ],
    }


def build_bundle(root=".", source_commit=None, now=None):
    root = Path(root).resolve()
    if source_commit is None:
        raise ValueError("source_commit_required_for_reproducibility")
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("timezone_aware_timestamp_required")
    pyproject_doc = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    py_dists = [
        (dist.metadata.get("Name"), dist.version)
        for dist in importlib.metadata.distributions()
        if dist.metadata.get("Name")
    ]
    sbom = build_sbom(
        project=pyproject_doc["project"],
        constraints=(root / "constraints-ci.txt").read_text(encoding="utf-8"),
        distributions=py_dists,
        source_commit=source_commit,
        now=timestamp,
    )
    lock_path = root / "apps/clinician-web/package-lock.json"
    node_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    node_components = _node_components(node_lock)
    sbom["components"].extend(node_components)
    sbom["components"].sort(key=lambda x: (x["name"].lower(), x["version"], x["purl"]))
    inventory_digest = hashlib.sha256(
        json.dumps(sbom["components"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    sbom["serialNumber"] = (
        f"urn:uuid:{inventory_digest[:8]}-{inventory_digest[8:12]}-5{inventory_digest[13:16]}-a{inventory_digest[17:20]}-{inventory_digest[20:32]}"
    )
    sbom["metadata"]["properties"] = [
        {"name": "sourceCommit", "value": source_commit},
        {"name": "packageInventorySha256", "value": inventory_digest},
        {"name": "npmLockSha256", "value": _sha(lock_path)},
        {
            "name": "redaction",
            "value": "resolved package download URLs, install paths, hostnames, environment and raw package metadata omitted",
        },
    ]
    direct_node = node_lock.get("packages", {}).get("", {})
    direct_node_names = set(direct_node.get("dependencies", {})) | set(
        direct_node.get("devDependencies", {})
    )
    direct_node_refs = [
        component["bom-ref"]
        for component in node_components
        if component["name"] in direct_node_names
    ]
    sbom["dependencies"][0]["dependsOn"].extend(direct_node_refs)
    sbom["node_dependency_inventory"] = {
        "status": "generated_from_local_npm_package_lock",
        "lockfile_version": node_lock.get("lockfileVersion"),
        "component_count": len(node_components),
        "lockfile_sha256": _sha(lock_path),
    }
    licenses = _license_register(root, source_commit, sbom, node_lock)
    model_cards = generate_model_cards(str(root))
    model_cards["source_commit"] = source_commit
    model_cards["source_hashes"] = {
        "model_registry_sha256": _sha(root / "evaluation/model-registry.json"),
        "candidate_access_audit_sha256": _sha(
            root / "evaluation/candidate-access-audit.json"
        ),
    }
    model_license_by_id = {model["id"]: model for model in licenses["models"]}
    for card in model_cards["cards"]:
        license_entry = model_license_by_id.get(card["model_id"], {})
        card["license_metadata"] = license_entry.get("license_metadata")
        card["license_source"] = license_entry.get("license_source", "unknown")
        card["license_status"] = license_entry.get("license_status", "unknown")
        report_path = card.get("report")
        if report_path and (root / report_path).is_file():
            card["report_sha256"] = _sha(root / report_path)
    matrix = _architecture_matrix(root, source_commit)
    return {
        "sbom": sbom,
        "license_register": licenses,
        "model_cards": model_cards,
        "architecture_matrix": matrix,
    }


def write_bundle(root=".", output_dir="evaluation/supply-chain", source_commit=None):
    root = Path(root).resolve()
    output = root / output_dir
    names = {
        "sbom": "sbom-v1.json",
        "license_register": "license-register-v1.json",
        "model_cards": "model-cards-v2.json",
        "architecture_matrix": "architecture-compliance-matrix-v1.json",
    }
    paths = {key: output / name for key, name in names.items()}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError("supply-chain bundle output exists; choose a new version")
    bundle = build_bundle(root, source_commit=source_commit)
    output.mkdir(parents=True, exist_ok=True)
    for key, path in paths.items():
        path.write_text(
            json.dumps(bundle[key], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", default="evaluation/supply-chain")
    args = parser.parse_args()
    paths = write_bundle(output_dir=args.output_dir, source_commit=args.source_commit)
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
