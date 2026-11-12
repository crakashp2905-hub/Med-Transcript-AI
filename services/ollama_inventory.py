"""Read-only hashes of the two configured Qwen cache manifests and their blobs."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from services.engineering_status import sha256
from services.strict_json import loads

CONFIGURED = {
    "qwen2.5:1.5b": "65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b",
    "qwen2.5:7b": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
}


def inventory(root):
    raw_root = Path(root)
    if str(root).startswith(("\\\\", "//")) or raw_root.is_symlink():
        raise ValueError("nonlocal_or_linked_model_cache")
    root = raw_root.resolve()
    models = []
    blobs = {}
    observed = {}
    for name, expected in CONFIGURED.items():
        family, tag = name.split(":")
        manifest = root / "manifests/registry.ollama.ai/library" / family / tag
        row = {
            "model": name,
            "expected_manifest_sha256": expected,
            "automatic_download": False,
        }
        if not manifest.is_file():
            models.append(
                {**row, "status": "unavailable", "reason": "manifest_missing"}
            )
            continue
        if manifest.is_symlink() or not manifest.resolve().is_relative_to(root):
            raise ValueError("model_cache_escape")
        before = manifest.stat()
        observed[manifest] = (before.st_size, before.st_mtime_ns)
        digest = sha256(manifest)
        body = loads(manifest.read_bytes(), max_bytes=524288, max_depth=16)
        row.update(manifest_sha256=digest, blob_digests=[])
        if digest != expected:
            models.append(
                {
                    **row,
                    "status": "integrity_failed",
                    "reason": "manifest_digest_mismatch",
                }
            )
            continue
        parts = [body["config"], *body["layers"]]
        for part in parts:
            token = part["digest"]
            size = part["size"]
            if (
                not re.fullmatch(r"sha256:[a-f0-9]{64}", token)
                or type(size) is not int
                or size < 0
            ):
                raise ValueError("invalid_cached_blob_descriptor")
            row["blob_digests"].append(token)
            if token in blobs:
                if blobs[token]["expected_bytes"] != size:
                    raise ValueError("conflicting_cached_blob_size")
                continue
            blob = root / "blobs" / token.replace(":", "-")
            entry = {"digest": token, "expected_bytes": size}
            if not blob.is_file():
                entry["status"] = "unavailable"
            else:
                if blob.is_symlink() or not blob.resolve().is_relative_to(root):
                    raise ValueError("model_cache_escape")
                info = blob.stat()
                observed[blob] = (info.st_size, info.st_mtime_ns)
                measured = sha256(blob)
                entry.update(
                    bytes=info.st_size,
                    sha256=measured,
                    status="verified_bytes"
                    if measured == token[7:] and info.st_size == size
                    else "integrity_failed",
                )
            blobs[token] = entry
        row["status"] = (
            "contents_hashed_not_model_eligibility"
            if all(blobs[t]["status"] == "verified_bytes" for t in row["blob_digests"])
            else "unavailable_or_corrupt_blob"
        )
        models.append(row)
    if any(
        (p.stat().st_size, p.stat().st_mtime_ns) != state
        for p, state in observed.items()
    ):
        raise ValueError("model_cache_changed_during_inventory")
    return {
        "schema_version": "configured_local_ollama_inventory_v1",
        "models": models,
        "blobs": list(blobs.values()),
        "unique_blob_bytes": sum(b.get("bytes", 0) for b in blobs.values()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "code_sha256": sha256(__file__),
        "model_inference_performed": False,
        "external_calls_attempted": 0,
        "independent_clinical_gold": False,
        "clinical_release": False,
        "limitations": "Only the configured Qwen 1.5B/7B manifests and referenced blobs are inspected. Other cached models remain outside scope; byte hashes do not attest license approval or clinical eligibility.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = inventory(args.root)
    with Path(args.out).open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2)
