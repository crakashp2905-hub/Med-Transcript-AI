"""Per-encounter storage snapshots and deletion footprint accounting."""

from pathlib import Path


AUDIO_SUFFIXES = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".webm"}


def snapshot_storage(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("storage_snapshot_root_must_be_directory")
    files = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            files[relative] = {
                "bytes": path.stat().st_size,
                "audio": path.suffix.lower() in AUDIO_SUFFIXES,
            }
    return {
        "schema_version": "encounter_storage_snapshot_v1",
        "root_label": root.name,
        "files": dict(sorted(files.items())),
        "file_count": len(files),
        "total_bytes": sum(row["bytes"] for row in files.values()),
        "audio_bytes": sum(row["bytes"] for row in files.values() if row["audio"]),
    }


def compare_encounter_storage(encounter_id, before, after):
    if (
        not isinstance(encounter_id, str)
        or not encounter_id
        or not isinstance(before, dict)
        or not isinstance(after, dict)
        or not isinstance(before.get("files"), dict)
        or not isinstance(after.get("files"), dict)
    ):
        raise ValueError("storage_comparison_inputs_invalid")
    old, new = before["files"], after["files"]
    added = sorted(new.keys() - old.keys())
    deleted = sorted(old.keys() - new.keys())
    changed = sorted(
        name
        for name in old.keys() & new.keys()
        if old[name]["bytes"] != new[name]["bytes"]
    )
    growth = sum(new[name]["bytes"] for name in added) + sum(
        new[name]["bytes"] - old[name]["bytes"] for name in changed
    )
    audio_retained = sum(row["bytes"] for row in new.values() if row["audio"])
    removed_bytes = sum(old[name]["bytes"] for name in deleted)
    return {
        "schema_version": "encounter_storage_delta_v1",
        "encounter_id": encounter_id,
        "before_total_bytes": before.get("total_bytes"),
        "after_total_bytes": after.get("total_bytes"),
        "net_storage_delta_bytes": after.get("total_bytes", 0)
        - before.get("total_bytes", 0),
        "added_or_grown_bytes": growth,
        "retained_audio_bytes_after": audio_retained,
        "deleted_file_count": len(deleted),
        "deleted_file_bytes": removed_bytes,
        "deleted_paths": deleted,
        "changed_paths": changed,
        "clinical_data_content_recorded": False,
    }
