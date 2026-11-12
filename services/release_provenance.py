"""Fail-closed binding between release code, data, acceptance and CI evidence."""

import hashlib
import json
import re
import subprocess
from pathlib import Path


COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_CI_JOBS = frozenset(
    {
        "test-dev-security",
        "test-dev-asr-security",
        "frontend",
        "postgres",
        "container",
    }
)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value):
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def build_acceptance_provenance(
    source_commit, source_files, dataset_manifests, ci_context=None
):
    if not isinstance(source_commit, str) or not COMMIT_RE.fullmatch(source_commit):
        raise ValueError("acceptance_commit_invalid")
    if not isinstance(source_files, dict) or not source_files:
        raise ValueError("acceptance_source_manifest_missing")
    if any(
        not isinstance(path, str)
        or not isinstance(digest, str)
        or not SHA256_RE.fullmatch(digest)
        for path, digest in source_files.items()
    ):
        raise ValueError("acceptance_source_manifest_invalid")
    if not isinstance(dataset_manifests, list) or not dataset_manifests:
        raise ValueError("acceptance_dataset_manifest_missing")
    datasets = []
    for item in dataset_manifests:
        path, digest = item.get("path"), item.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or not isinstance(digest, str)
            or not SHA256_RE.fullmatch(digest)
        ):
            raise ValueError("acceptance_dataset_manifest_invalid")
        datasets.append({"path": path, "manifest_sha256": digest})
    code_body = {
        "schema_version": "code_manifest_v1",
        "source_commit": source_commit,
        "files": source_files,
    }
    ci = {"status": "not_observed"}
    if ci_context:
        run_id = ci_context.get("run_id")
        job = ci_context.get("job")
        ci_commit = ci_context.get("source_commit")
        if not all(isinstance(value, str) and value for value in (run_id, job)):
            raise ValueError("ci_context_incomplete")
        if ci_commit != source_commit:
            raise ValueError("ci_context_commit_mismatch")
        ci = {
            "status": "observed_context_only",
            "provider": ci_context.get("provider", "github-actions"),
            "run_id": run_id,
            "attempt": ci_context.get("attempt"),
            "job": job,
            "workflow": ci_context.get("workflow"),
            "ref": ci_context.get("ref"),
            "source_commit": ci_commit,
        }
    return {
        "source_commit": source_commit,
        "code_manifest_sha256": canonical_sha256(code_body),
        "dataset_manifests": datasets,
        "ci_context": ci,
    }


def _file(root, entry, expected_sha, label):
    if not isinstance(entry, str) or not entry or Path(entry).is_absolute():
        raise ValueError(f"{label}_path_invalid")
    path = (root / entry).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"{label}_path_missing_or_external")
    actual = sha256_bytes(path.read_bytes())
    if not isinstance(expected_sha, str) or actual != expected_sha:
        raise ValueError(f"{label}_sha256_mismatch")
    return path


def _validate_commit_tree(root, commit, files):
    for relative, expected in files.items():
        path = _file(root, relative, expected, "code_file")
        try:
            committed = subprocess.check_output(
                ["git", "show", f"{commit}:{relative}"],
                cwd=root,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError("code_manifest_commit_file_missing") from exc
        if sha256_bytes(committed) != sha256_bytes(path.read_bytes()):
            raise ValueError("code_manifest_not_exact_commit_tree")


def validate_release_candidate(candidate, root="."):
    """Validate hashes and shared ancestry before a release candidate is admitted.

    CI log digests establish byte integrity and shared run metadata. The function
    does not authenticate a CI provider or infer that a run actually occurred.
    """
    root = Path(root).resolve()
    if not isinstance(candidate, dict) or candidate.get("schema_version") != (
        "release_candidate_binding_v1"
    ):
        raise ValueError("release_candidate_schema_invalid")
    commit = candidate.get("source_commit")
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        raise ValueError("release_candidate_commit_invalid")

    code_ref = candidate.get("code_manifest", {})
    code_path = _file(
        root, code_ref.get("path"), code_ref.get("sha256"), "code_manifest"
    )
    code = json.loads(code_path.read_text(encoding="utf-8"))
    if code.get("schema_version") != "code_manifest_v1":
        raise ValueError("code_manifest_schema_invalid")
    if code.get("source_commit") != commit:
        raise ValueError("code_manifest_commit_mismatch")
    files = code.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("code_manifest_files_missing")
    digest_body = {
        "schema_version": code["schema_version"],
        "source_commit": commit,
        "files": files,
    }
    if code.get("manifest_sha256") != canonical_sha256(digest_body):
        raise ValueError("code_manifest_digest_mismatch")
    _validate_commit_tree(root, commit, files)

    acceptance_ref = candidate.get("acceptance_report", {})
    acceptance_path = _file(
        root,
        acceptance_ref.get("path"),
        acceptance_ref.get("sha256"),
        "acceptance_report",
    )
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    if acceptance.get("source_commit") != commit:
        raise ValueError("acceptance_commit_mismatch")
    if acceptance.get("source_sha256") != files:
        raise ValueError("acceptance_code_manifest_mismatch")
    if acceptance.get("code_manifest_sha256") != code["manifest_sha256"]:
        raise ValueError("acceptance_code_manifest_digest_mismatch")

    dataset_refs = candidate.get("dataset_manifests")
    if not isinstance(dataset_refs, list) or not dataset_refs:
        raise ValueError("dataset_manifest_missing")
    dataset_hashes = {}
    for item in dataset_refs:
        manifest_path = _file(
            root,
            item.get("manifest_path"),
            item.get("manifest_sha256"),
            "dataset_manifest",
        )
        protocol_path = _file(
            root,
            item.get("protocol_path"),
            item.get("protocol_sha256"),
            "dataset_protocol",
        )
        lock_path = _file(
            root, item.get("lock_path"), item.get("lock_sha256"), "dataset_lock"
        )
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock.get("manifest_sha256") != item["manifest_sha256"]:
            raise ValueError("dataset_lock_manifest_mismatch")
        if lock.get("protocol_sha256") != item["protocol_sha256"]:
            raise ValueError("dataset_lock_protocol_mismatch")
        dataset_hashes[item["manifest_path"]] = sha256_bytes(manifest_path.read_bytes())
        dataset_hashes[item["protocol_path"]] = sha256_bytes(protocol_path.read_bytes())

    provenance = acceptance.get("provenance", {})
    if provenance.get("code_manifest_sha256") != code["manifest_sha256"]:
        raise ValueError("acceptance_provenance_code_mismatch")
    accepted_datasets = {
        item.get("manifest_sha256")
        for item in provenance.get("dataset_manifests", [])
        if isinstance(item, dict)
    }
    if not accepted_datasets or not accepted_datasets.issubset(
        {item["manifest_sha256"] for item in dataset_refs}
    ):
        raise ValueError("acceptance_provenance_dataset_mismatch")

    ci = candidate.get("ci_run", {})
    run_id = ci.get("run_id")
    jobs = ci.get("jobs")
    if not isinstance(run_id, str) or not run_id or not isinstance(jobs, list):
        raise ValueError("ci_run_metadata_missing")
    seen = set()
    log_hashes = {}
    for job in jobs:
        name = job.get("name")
        if name not in REQUIRED_CI_JOBS or name in seen:
            raise ValueError("ci_job_name_duplicate_or_unknown")
        seen.add(name)
        if job.get("run_id") != run_id or job.get("source_commit") != commit:
            raise ValueError("ci_job_ancestry_mismatch")
        if job.get("conclusion") != "success":
            raise ValueError("ci_job_not_successful")
        log_path = _file(root, job.get("log_path"), job.get("log_sha256"), "ci_log")
        try:
            log_record = json.loads(log_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("ci_log_record_invalid") from exc
        if (
            log_record.get("schema_version") != "ci_job_log_binding_v1"
            or log_record.get("name") != name
            or log_record.get("run_id") != run_id
            or log_record.get("source_commit") != commit
            or log_record.get("conclusion") != "success"
            or log_record.get("code_manifest_sha256") != code["manifest_sha256"]
        ):
            raise ValueError("ci_log_metadata_mismatch")
        log_datasets = {
            item.get("manifest_sha256")
            for item in log_record.get("dataset_manifests", [])
            if isinstance(item, dict)
        }
        if not accepted_datasets.issubset(log_datasets):
            raise ValueError("ci_log_dataset_binding_mismatch")
        log_hashes[name] = sha256_bytes(log_path.read_bytes())
    if seen != REQUIRED_CI_JOBS:
        raise ValueError("ci_job_set_incomplete")
    if any(
        job.get("status") != "pass" for job in acceptance.get("checks", {}).values()
    ):
        raise ValueError("acceptance_report_not_passing")
    binding = {
        "schema_version": "validated_release_binding_v1",
        "source_commit": commit,
        "code_manifest_sha256": code["manifest_sha256"],
        "acceptance_report_sha256": acceptance_ref["sha256"],
        "dataset_hashes": dataset_hashes,
        "ci_run_id": run_id,
        "ci_log_sha256": log_hashes,
        "real_patient_release_authorized": False,
    }
    return {**binding, "binding_sha256": canonical_sha256(binding)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", help="Path to the release candidate binding JSON")
    parser.add_argument(
        "--root", default=".", help="Repository root for bound evidence"
    )
    args = parser.parse_args()
    path = Path(args.candidate)
    if path.is_absolute():
        raise SystemExit("candidate_path_must_be_relative")
    candidate_path = (Path(args.root).resolve() / path).resolve()
    if not candidate_path.is_relative_to(Path(args.root).resolve()):
        raise SystemExit("candidate_path_outside_root")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    print(json.dumps(validate_release_candidate(candidate, args.root), indent=2))


if __name__ == "__main__":
    main()
