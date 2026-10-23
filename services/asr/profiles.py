"""Hash local converted model artifacts without downloading or accepting terms."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.api.ingest import file_sha256


REQUIRED_FILES = {"model.bin", "config.json", "tokenizer.json"}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_sha256(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class ASRProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    profile_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    engine: Literal["faster-whisper"] = "faster-whisper"
    runtime_version: Literal["1.2.1"] = "1.2.1"
    model_dir: str = Field(min_length=1, max_length=2048)
    source: str = Field(min_length=1, max_length=200)
    revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    license_id: str = Field(min_length=1, max_length=100)
    artifacts: dict[str, str] = Field(min_length=3, max_length=128)
    device: Literal["cpu", "cuda"] = "cpu"
    compute_type: Literal["int8", "float32", "float16", "int8_float16"] = "int8"
    cpu_threads: int = Field(default=4, ge=1, le=32, strict=True)
    beam_size: int = Field(default=5, ge=1, le=10, strict=True)
    language: Literal["en"] = "en"
    input_profile: Literal["mono_16khz_pcm_s16le"] = "mono_16khz_pcm_s16le"
    clinical_validation: Literal["not_validated"] = "not_validated"

    @field_validator("model_dir")
    @classmethod
    def absolute_directory(cls, value):
        if not Path(value).is_absolute():
            raise ValueError("An absolute local model directory is required")
        return value

    @field_validator("artifacts")
    @classmethod
    def bounded_filenames(cls, value):
        if not REQUIRED_FILES <= value.keys():
            raise ValueError("Required model/config/tokenizer artifacts are missing")
        for name, digest in value.items():
            if name in (".", "..") or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", name):
                raise ValueError("Artifact names must be plain filenames")
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("Artifact SHA-256 is required")
        return value

    @property
    def sha256(self):
        return content_sha256(self.model_dump(mode="json"))

    def verify_artifacts(self):
        root = Path(self.model_dir)
        if not root.is_dir() or root.is_symlink():
            raise ValueError("model_integrity_failure")
        files = {item.name for item in root.iterdir() if item.is_file() or item.is_symlink()}
        if files != self.artifacts.keys():
            raise ValueError("model_integrity_failure")
        for name, expected in self.artifacts.items():
            path = root / name
            if path.is_symlink() or not path.is_file() or file_sha256(path) != expected:
                raise ValueError("model_integrity_failure")


def load_profiles(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw or len(raw) > 20:
        raise ValueError("Supply a nonempty JSON array of at most 20 profiles")
    profiles = [ASRProfile.model_validate(item) for item in raw]
    if len({profile.profile_id for profile in profiles}) != len(profiles):
        raise ValueError("Profile IDs must be unique")
    return {profile.profile_id: profile for profile in profiles}


def main():
    parser = argparse.ArgumentParser(description="Manifest already provisioned local faster-whisper artifacts")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--license-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.model_dir).resolve(strict=True)
    artifacts = {item.name: file_sha256(item) for item in root.iterdir() if item.is_file()}
    profile = ASRProfile(profile_id=args.profile_id, model_dir=str(root), source=args.source,
                         revision=args.revision, license_id=args.license_id, artifacts=artifacts)
    profile.verify_artifacts()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Avoid overwriting an existing profile configuration by mistake.
    with output.open("x", encoding="utf-8") as target:
        json.dump([profile.model_dump(mode="json")], target, indent=2)
    print(json.dumps({"profile_id": profile.profile_id, "sha256": profile.sha256, "status": "manifested_not_validated"}))


if __name__ == "__main__":
    main()
