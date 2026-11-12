"""Reproduce the offline safety test lane from a committed snapshot in temp storage."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


DEFAULT_TESTS = ("tests/test_clean_repro.py",)


def materialize_commit(repo, destination):
    """Extract git archive files into an empty directory without links or traversal."""
    repo = Path(repo).resolve()
    destination = Path(destination).resolve()
    if destination == repo or destination.is_relative_to(repo):
        raise ValueError("clean_repro_destination_inside_repository")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("clean_repro_destination_not_empty")
    destination.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                if (
                    name.is_absolute()
                    or ".." in name.parts
                    or not (member.isdir() or member.isfile())
                ):
                    raise ValueError("clean_repro_unsafe_archive_member")
                target = (destination / Path(*name.parts)).resolve()
                if not target.is_relative_to(destination):
                    raise ValueError("clean_repro_unsafe_archive_member")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("clean_repro_archive_file_unreadable")
                with source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
        stderr = process.stderr.read() if process.stderr else b""
        if process.wait() != 0:
            raise RuntimeError("git_archive_failed: " + stderr.decode(errors="replace"))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def run(repo=".", all_tests=False, timeout_seconds=1200):
    repo = Path(repo).resolve()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if temp_root == repo or temp_root.is_relative_to(repo):
        raise ValueError("system_temp_directory_inside_repository")
    with tempfile.TemporaryDirectory(prefix="med-transcript-clean-repro-") as raw:
        snapshot = Path(raw) / "source"
        materialize_commit(repo, snapshot)
        tests = ("tests",) if all_tests else DEFAULT_TESTS
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(Path(raw) / "pytest-temp"),
            *tests,
        ]
        env = {
            **os.environ,
            "MED_TRANSCRIPT_OFFLINE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        try:
            result = subprocess.run(
                command,
                cwd=snapshot,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
            exit_code = result.returncode
            output = result.stdout
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            timed_out = True
        lines = output.splitlines()
        summary = next(
            (
                line.strip()
                for line in reversed(lines)
                if " passed" in line or " failed" in line
            ),
            "pytest produced no summary",
        )
        return {
            "schema_version": "clean_directory_repro_v1",
            "source_commit": commit,
            "suite": "all_tests" if all_tests else "clean_repro_self_tests",
            "exit_code": exit_code,
            "summary": summary,
            "timed_out": timed_out,
            "repository_modified": False,
            "previous_evidence_modified": False,
            "original_production_fixtures_modified": False,
            "snapshot_location": "temporary_directory_removed_after_run",
            "network_fetches_allowed": False,
            "raw_test_output_included": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--all-tests", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    args = parser.parse_args()
    result = run(args.repo, args.all_tests, args.timeout_seconds)
    print(json.dumps(result, indent=2))
    raise SystemExit(result["exit_code"])
