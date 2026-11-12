"""Local redacted leak scanner. Findings contain locations and types, never values."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PATTERNS = {
    "private_key_material": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}\b"),
    "assigned_secret": re.compile(
        r"""(?i)(?:access_key|client_secret|api_key|password)["']?\s*[:=]\s*["']([A-Za-z0-9_+/=-]{24,})["']"""
    ),
}


def inspect_text(text, path, known_secrets=()):
    findings = []
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group()
            if value.startswith(("REPLACE_", "EXAMPLE_", "synthetic-", "simulated-")):
                continue
            findings.append(
                {
                    "path": path,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "type": kind,
                }
            )
    for value in known_secrets:
        if value and len(value) >= 24 and value in text:
            findings.append(
                {
                    "path": path,
                    "line": text.count("\n", 0, text.index(value)) + 1,
                    "type": "known_local_credential",
                }
            )
    return findings


def scan(root="."):
    root = Path(root).resolve()
    names = set(
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            text=True,
        ).splitlines()
    )
    # Built browser bundles are ignored by Git but are distributed to users.
    for directory in ("apps/clinician-web/dist", "evaluation/reports"):
        for candidate in (root / directory).rglob("*"):
            if candidate.is_file():
                names.add(candidate.relative_to(root).as_posix())
    known = []
    local = root / "data/local-config.json"
    if local.is_file():
        body = json.loads(local.read_text(encoding="utf-8"))
        known = [body.get("access_key", "")]
    results, files = [], []
    for name in sorted(names):
        path = (root / name).resolve()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.suffix.lower() in (".wav", ".flac", ".mp3", ".png", ".jpg", ".zip")
        ):
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        files.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest()})
        results.extend(inspect_text(text, name, known))
    return {
        "schema_version": "redacted_secret_scan_v1",
        "files": files,
        "findings": results,
        "status": "pass" if not results else "fail",
        "secret_values_included": False,
        "limitations": "Pattern and known-local-key scanning is not proof that no secret or patient identifier exists.",
        "real_patient_release_authorized": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = scan()
    with Path(args.out).open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
    if report["findings"]:
        raise SystemExit(1)
