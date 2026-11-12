"""Versioned allowlist for local development and benchmark artifacts."""

import json
from pathlib import Path

from services.engineering_status import sha256

POLICY_PATH = Path("evaluation/contracts/artifact-scope-v1.json")


def load_policy(root="."):
    root = Path(root).resolve()
    path = root / POLICY_PATH
    if not path.is_file():
        return {
            "status": "blocked_missing_local_artifact",
            "policy_path": POLICY_PATH.as_posix(),
            "clinical_release_authorized": False,
        }
    policy = json.loads(path.read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != "artifact_scope_v1"
        or policy.get("clinical_release_authorized") is not False
        or not policy.get("permitted")
        or not policy.get("prohibited")
    ):
        raise ValueError("artifact_scope_policy_invalid")
    prefixes = []
    for item in policy["permitted"]:
        if not item.get("id") or not item.get("conditions"):
            raise ValueError("artifact_scope_policy_invalid")
        for prefix in item.get("path_prefixes", []):
            normalized = Path(prefix).as_posix()
            if normalized.startswith("/") or ".." in Path(normalized).parts:
                raise ValueError("artifact_scope_policy_invalid")
            prefixes.append(normalized)
    if len(prefixes) != len(set(prefixes)):
        raise ValueError("artifact_scope_policy_invalid")
    return {
        "status": "available",
        "schema_version": policy["schema_version"],
        "policy_path": POLICY_PATH.as_posix(),
        "policy_sha256": sha256(path),
        "permitted_categories": [item["id"] for item in policy["permitted"]],
        "prohibited_sources": policy["prohibited"],
        "clinical_release_authorized": False,
    }


def classify_path(relative_path, root="."):
    root = Path(root).resolve()
    relative = Path(relative_path)
    candidate = root / relative
    if relative.is_absolute() or not candidate.resolve().is_relative_to(root):
        raise ValueError("artifact_scope_path_escape")
    current = candidate
    while current != root:
        if current.is_symlink():
            raise ValueError("artifact_scope_symlink_forbidden")
        current = current.parent
    policy = json.loads((root / POLICY_PATH).read_text(encoding="utf-8"))
    normalized = relative.as_posix().rstrip("/") + "/"
    for item in policy["permitted"]:
        if any(normalized.startswith(prefix) for prefix in item["path_prefixes"]):
            return {"status": "permitted", "category": item["id"]}
    return {"status": "prohibited_or_unclassified", "category": None}
