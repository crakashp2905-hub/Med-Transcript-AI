"""Build a redacted local Python SBOM without contacting package services."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import tomllib


ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")


def normalize_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_constraints(text):
    pins = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*==\s*([^;\s]+)", line)
        if match:
            pins[normalize_name(match.group(1))] = match.group(2)
    return pins


def requirement_names(project):
    required = set()
    optional = set()
    for requirement in project.get("dependencies", []):
        match = NAME_RE.match(requirement)
        if match:
            required.add(normalize_name(match.group(1)))
    for requirements in project.get("optional-dependencies", {}).values():
        for requirement in requirements:
            match = NAME_RE.match(requirement)
            if match:
                optional.add(normalize_name(match.group(1)))
    return required, optional


def advisory_freshness(cache_path, *, now=None):
    if not cache_path:
        return {
            "status": "unavailable",
            "age_days": None,
            "database": None,
            "reason": "No local advisory cache was configured; no vulnerability scan was performed.",
        }
    path = Path(cache_path)
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        timestamp = body.get("fetched_at") or body.get("updated_at")
        recorded = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if recorded.tzinfo is None:
            raise ValueError("timestamp_timezone_missing")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {
            "status": "invalid_cache_metadata",
            "age_days": None,
            "database": path.name,
            "reason": "The supplied local cache lacks a valid timezone-aware update timestamp.",
        }
    current = now or datetime.now(timezone.utc)
    age = (current - recorded.astimezone(timezone.utc)).total_seconds() / 86400
    if age < 0:
        return {
            "status": "invalid_cache_metadata",
            "age_days": None,
            "database": path.name,
            "reason": "The supplied cache timestamp is in the future.",
        }
    return {
        "status": "available_metadata_only",
        "age_days": round(age, 2),
        "database": path.name,
        "reason": "Cache timestamp measured; advisory matching requires a separately implemented offline scanner.",
    }


def build_sbom(
    *, project, constraints, distributions, source_commit, advisory_cache=None, now=None
):
    pins = parse_constraints(constraints)
    required, optional = requirement_names(project)
    components = []
    for name, version in sorted(
        ((name, version) for name, version in distributions),
        key=lambda item: (normalize_name(item[0]), item[1]),
    ):
        normalized = normalize_name(name)
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "bom-ref": f"pkg:pypi/{normalized}@{version}",
                "purl": f"pkg:pypi/{normalized}@{version}",
                "scope": "required" if normalized not in optional else "optional",
                "dependency_class": "direct_required"
                if normalized in required
                else "direct_optional"
                if normalized in optional
                else "installed_transitive_or_tooling",
                "inventory_status": "pinned_match"
                if normalized in pins and pins[normalized] == version
                else "pinned_mismatch"
                if normalized in pins
                else "installed_unpinned",
                "constraint_version": pins.get(normalized),
            }
        )
    missing_pins = sorted(set(pins) - {normalize_name(n) for n, _ in distributions})
    created = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    root_ref = f"pkg:pypi/{normalize_name(project['name'])}@{project['version']}"
    package_digest = hashlib.sha256(
        json.dumps(components, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{package_digest[:8]}-{package_digest[8:12]}-5{package_digest[13:16]}-a{package_digest[17:20]}-{package_digest[20:32]}",
        "version": 1,
        "metadata": {
            "timestamp": created.isoformat(),
            "tools": [{"name": "med-transcript-ai-offline-sbom", "version": "1"}],
            "component": {
                "type": "application",
                "name": project["name"],
                "version": project["version"],
                "bom-ref": root_ref,
                "purl": root_ref,
            },
            "properties": [
                {"name": "sourceCommit", "value": source_commit},
                {"name": "packageInventorySha256", "value": package_digest},
                {
                    "name": "redaction",
                    "value": "install paths, hostnames, environment and raw package metadata omitted",
                },
            ],
        },
        "components": components,
        "dependencies": [
            {
                "ref": root_ref,
                "dependsOn": [
                    c["bom-ref"]
                    for c in components
                    if c["scope"] in {"required", "optional"}
                ],
            }
        ],
        "offline_dependency_inventory": {
            "status": "generated",
            "installed_component_count": len(components),
            "constraint_pin_count": len(pins),
            "missing_pinned_packages": missing_pins,
            "pinned_version_mismatches": [
                c["name"]
                for c in components
                if c["inventory_status"] == "pinned_mismatch"
            ],
        },
        "advisory_database": advisory_freshness(advisory_cache, now=now),
        "vulnerability_assessment": {
            "status": "not_performed",
            "safe_to_use": None,
            "reason": "An SBOM is not a vulnerability scan; no package is represented as audited or safe.",
        },
        "source_commit": source_commit,
        "redacted": True,
    }


def generate(output, advisory_cache=None):
    target = Path(output)
    if target.exists():
        raise FileExistsError(
            "SBOM output exists; choose a new path to preserve prior evidence"
        )
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    constraints = (ROOT / "constraints-ci.txt").read_text(encoding="utf-8")
    distributions = [
        (dist.metadata.get("Name"), dist.version)
        for dist in importlib.metadata.distributions()
        if dist.metadata.get("Name")
    ]
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result = build_sbom(
        project=pyproject["project"],
        constraints=constraints,
        distributions=distributions,
        source_commit=commit,
        advisory_cache=advisory_cache,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "source_commit": commit,
                "installed_component_count": len(result["components"]),
                "missing_pinned_packages": len(
                    result["offline_dependency_inventory"]["missing_pinned_packages"]
                ),
                "advisory_database_status": result["advisory_database"]["status"],
                "vulnerability_assessment": "not_performed",
                "output": target.name,
            },
            sort_keys=True,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--advisory-cache")
    args = parser.parse_args()
    generate(args.output, args.advisory_cache)


if __name__ == "__main__":
    main()
