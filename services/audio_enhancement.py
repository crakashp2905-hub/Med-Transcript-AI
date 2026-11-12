"""Source-preserving boundary for experimental audio enhancement candidates."""

import os
from pathlib import Path
import shutil
import tempfile

from services.audio_provenance import (
    derive_provenance,
    file_sha256,
    source_provenance,
)


def prepare_candidate(
    source_path,
    candidate_path=None,
    enhancement_id=None,
    transform=None,
    parameters=None,
    timeline_mapping=None,
):
    """Return source audio unchanged or publish a distinct derived candidate."""
    source = Path(source_path).resolve()
    source_receipt = source_provenance(source)
    original_sha256 = source_receipt["asset_sha256"]
    if enhancement_id is None:
        if any(
            value is not None for value in (transform, parameters, timeline_mapping)
        ):
            raise ValueError("disabled_enhancement_cannot_accept_transform")
        return {
            "candidate_path": str(source),
            "candidate_sha256": original_sha256,
            "enhancement_id": "disabled",
            "enhancement_applied": False,
            "audio_provenance": source_receipt,
        }

    if (
        not isinstance(enhancement_id, str)
        or not enhancement_id.strip()
        or not callable(transform)
        or not isinstance(parameters, dict)
        or not isinstance(timeline_mapping, dict)
        or candidate_path is None
    ):
        raise ValueError("incomplete_enhancement_candidate")
    target = Path(candidate_path).resolve()
    if target == source or target.exists():
        raise ValueError("enhancement_candidate_must_be_a_new_file")
    if not target.parent.is_dir():
        raise ValueError("enhancement_candidate_directory_required")

    staging = snapshot = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".audio-candidate-",
            suffix=target.suffix or ".wav",
            dir=target.parent,
            delete=False,
        ) as temporary:
            staging = Path(temporary.name)
        with tempfile.NamedTemporaryFile(
            prefix=".audio-source-snapshot-",
            suffix=source.suffix or ".wav",
            dir=target.parent,
            delete=False,
        ) as temporary:
            snapshot = Path(temporary.name)
        shutil.copyfile(source, snapshot)
        if file_sha256(snapshot) != original_sha256:
            raise ValueError("source_snapshot_integrity_failure")
        transform(snapshot, staging)
        if not staging.is_file() or staging.stat().st_size == 0:
            raise ValueError("enhancement_candidate_output_required")
        if file_sha256(source) != original_sha256:
            raise ValueError("source_audio_changed_during_enhancement")
        if file_sha256(snapshot) != original_sha256:
            raise ValueError("enhancement_input_snapshot_changed")
        receipt = derive_provenance(
            source_receipt,
            staging,
            enhancement_id,
            parameters,
            timeline_mapping,
        )
        os.rename(staging, target)
        staging = None
        if file_sha256(target) != receipt["asset_sha256"]:
            target.unlink(missing_ok=True)
            raise ValueError("enhancement_candidate_changed_after_publish")
        return {
            "candidate_path": str(target),
            "candidate_sha256": receipt["asset_sha256"],
            "enhancement_id": enhancement_id,
            "enhancement_applied": True,
            "source_sha256": original_sha256,
            "audio_provenance": receipt,
        }
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)
        if snapshot is not None:
            snapshot.unlink(missing_ok=True)
