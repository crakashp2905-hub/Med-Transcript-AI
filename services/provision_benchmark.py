"""Explicit, revision-pinned public model downloads for benchmark use only."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.profiles import ASRProfile


def provision(repo, revision, destination, filenames, profile_id=None, license_id=None):
    from huggingface_hub import HfApi
    info = HfApi().model_info(repo, revision=revision, files_metadata=True, token=False)
    if info.sha != revision or info.gated:
        raise ValueError("Only pinned ungated public artifacts are supported")
    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lookup = {f.rfilename: f for f in info.siblings}
    receipts = []
    for name in filenames:
        source = lookup[name]
        target = root / name
        if not target.resolve().is_relative_to(root):
            raise ValueError("Invalid artifact path")
        target.parent.mkdir(parents=True, exist_ok=True)
        def matches(path):
            if not path.is_file() or path.stat().st_size != source.size:
                return False
            if source.lfs:
                return file_sha256(path) == source.lfs.sha256
            body = path.read_bytes()
            return hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest() == source.blob_id
        if not matches(target):
            partial = target.with_name(target.name + ".partial")
            url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}?download=true"
            with urllib.request.urlopen(url, timeout=90) as response, partial.open("wb") as output:
                count = 0
                while block := response.read(4 * 1024 * 1024):
                    count += len(block)
                    if count > source.size:
                        raise ValueError("Download exceeded pinned artifact size")
                    output.write(block)
            if not matches(partial):
                raise ValueError("Downloaded artifact integrity failure")
            partial.replace(target)
        receipts.append({"filename": name, "sha256": file_sha256(target), "bytes": source.size})
        print(f"Verified {repo}/{name}", flush=True)
    if profile_id:
        if any("/" in name for name in filenames):
            raise ValueError("Converted runtime profiles require root artifacts")
        profile = ASRProfile(profile_id=profile_id, model_dir=str(root), source=repo,
            revision=revision, license_id=license_id,
            artifacts={r["filename"]: r["sha256"] for r in receipts})
        profile.verify_artifacts()
        Path(f"data/{profile_id}-profiles.json").write_text(json.dumps([profile.model_dump()], indent=2), encoding="utf-8")
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--profile-id")
    parser.add_argument("--license-id")
    args = parser.parse_args()
    provision(args.repo, args.revision, args.destination, args.files, args.profile_id, args.license_id)


if __name__ == "__main__":
    main()
