"""Create a group-disjoint, source-bound research split from local licensed data."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from services.audio_provenance import file_sha256
from services.immutable_reports import publish_json_once


ROOT = Path("evaluation/datasets")
SOURCE_NAMES = (
    "primock57-expanded-v1",
    "primock57-validation-v1",
    "primock57-smoke-v1",
    "meddistract-detailed-v1",
)
OUTPUT = Path("evaluation/runs/asr-training-splits/group-split-v1.json")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _reference(row, is_case):
    if is_case:
        return " ".join(
            re.sub(r"<[^>]+>", "", turn["reference"])
            for turn in row.get("reference_turns", [])
        )
    return row.get("reference", "")


def assign_group_splits(training_candidates, development_groups, reserved_groups):
    """Return explicit group assignments; a group can belong to only one split."""
    training_candidates = set(training_candidates)
    development_groups = set(development_groups)
    reserved_groups = set(reserved_groups)
    if (
        not training_candidates
        or training_candidates & development_groups
        or training_candidates & reserved_groups
        or development_groups & reserved_groups
    ):
        raise ValueError("training_development_acceptance_groups_must_be_disjoint")
    assignments = {group: "development" for group in development_groups}
    assignments.update({group: "reserved_acceptance" for group in reserved_groups})
    assignments.update({group: "training" for group in training_candidates})
    return assignments


def _manifest_rows(name, manifest):
    rows = manifest.get("samples", manifest.get("cases", []))
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty_source_samples_required")
    result = []
    is_case = "cases" in manifest
    for row in rows:
        primary = row.get("foreground_id") or row.get("group_id")
        if not isinstance(primary, str) or not primary:
            raise ValueError("original_consultation_group_required")
        contributors = [primary]
        donor = row.get("donor_id")
        if donor:
            if not isinstance(donor, str):
                raise ValueError("donor_consultation_group_invalid")
            contributors.append(donor)
        audio = row.get("audio")
        audio_sha = row.get("audio_sha256")
        reference = _reference(row, is_case)
        if (
            not isinstance(audio, str)
            or not isinstance(audio_sha, str)
            or len(audio_sha) != 64
            or not isinstance(reference, str)
            or not reference.strip()
        ):
            raise ValueError("audio_hash_and_reference_required")
        result.append(
            {
                "sample_id": row.get("sample_id") or row.get("group_id"),
                "consultation_group_id": primary,
                "contributing_group_ids": sorted(set(contributors)),
                "audio": audio,
                "audio_sha256": audio_sha,
                "reference_sha256": hashlib.sha256(
                    reference.encode("utf-8")
                ).hexdigest(),
                "condition": row.get("condition", "clean"),
            }
        )
    return result


def build_training_split(
    dataset_root=ROOT,
    reservation_path=Path("evaluation/acceptance-reservation-v1.json"),
):
    dataset_root = Path(dataset_root)
    reservation_path = Path(reservation_path)
    reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
    reserved = set(reservation.get("reserved_groups", []))
    if not reserved:
        raise ValueError("reserved_acceptance_groups_required")

    manifests = {}
    inventory = []
    for name in SOURCE_NAMES:
        manifest_path = dataset_root / name / "manifest.json"
        lock_path = dataset_root / name / "lock.json"
        if not manifest_path.is_file() or not lock_path.is_file():
            raise ValueError("source_manifest_and_lock_required")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        manifest_sha = _sha(manifest_path)
        if lock.get("manifest_sha256") != manifest_sha:
            raise ValueError("source_manifest_lock_mismatch")
        if (
            manifest.get("rights_reviewed") is not True
            or manifest.get("license_id", manifest.get("license")) != "CC-BY-4.0"
            or manifest.get("data_class") != "approved_public"
        ):
            raise ValueError("rights_reviewed_cc_by_development_source_required")
        manifests[name] = manifest
        inventory.append(
            {
                "name": name,
                "dataset_id": manifest.get("dataset_id"),
                "manifest_sha256": manifest_sha,
                "lock_sha256": _sha(lock_path),
                "license": manifest.get("license_id", manifest.get("license")),
                "split_role_before_partition": manifest.get(
                    "split_role", manifest.get("split")
                ),
                "sample_count": len(manifest.get("samples", manifest.get("cases", []))),
            }
        )

    development_groups = set()
    for name in (
        "primock57-validation-v1",
        "primock57-smoke-v1",
        "meddistract-detailed-v1",
    ):
        for row in _manifest_rows(name, manifests[name]):
            development_groups.update(row["contributing_group_ids"])

    expanded_groups = {
        row["consultation_group_id"]
        for row in _manifest_rows(
            "primock57-expanded-v1", manifests["primock57-expanded-v1"]
        )
    }
    if expanded_groups & reserved:
        raise ValueError("reserved_acceptance_group_present_in_development_manifest")
    training_groups = expanded_groups - development_groups - reserved
    assignments = assign_group_splits(training_groups, development_groups, reserved)

    split_rows = []
    seen_ids = set()
    seen_audio_splits = {}
    for name, manifest in manifests.items():
        rows = _manifest_rows(name, manifest)
        for row in rows:
            if row["sample_id"] in seen_ids:
                raise ValueError("duplicate_source_sample_id_across_manifests")
            seen_ids.add(row["sample_id"])
            row_splits = {
                assignments.get(group) for group in row["contributing_group_ids"]
            }
            if len(row_splits) != 1 or None in row_splits:
                raise ValueError("source_and_donor_groups_cross_split_boundary")
            split = row_splits.pop()
            if split == "reserved_acceptance":
                raise ValueError("reserved_acceptance_data_must_not_be_loaded")
            audio_path = dataset_root / name / row["audio"]
            if not audio_path.is_file():
                alternative = Path("data/datasets") / name / row["audio"]
                if alternative.is_file():
                    audio_path = alternative
                else:
                    raise ValueError("local_training_split_audio_missing")
            if file_sha256(audio_path) != row["audio_sha256"]:
                raise ValueError("local_training_split_audio_hash_mismatch")
            prior = seen_audio_splits.setdefault(row["audio_sha256"], split)
            if prior != split:
                raise ValueError("duplicate_audio_crosses_split_boundary")
            split_rows.append(
                {
                    **row,
                    "split": split,
                    "source_dataset": name,
                    "source_audio_path": audio_path.as_posix(),
                    "parent_group_split_inherited": True,
                }
            )

    counts = {
        split: sum(row["split"] == split for row in split_rows)
        for split in ("training", "development")
    }
    split_groups = {
        split: sorted(group for group, value in assignments.items() if value == split)
        for split in ("training", "development", "reserved_acceptance")
    }
    return {
        "schema_version": "asr_original_consultation_group_split_v1",
        "complete": True,
        "clinical_acceptance": False,
        "acceptance_labels_accessed": False,
        "inference_executed": False,
        "audio_transformed": False,
        "source_commit": _commit(),
        "split_method": "group-exclusive; development holdout plus donor dependency closure",
        "manifest_sources": inventory,
        "reservation_sha256": _sha(reservation_path),
        "group_assignments": split_groups,
        "group_counts": {split: len(groups) for split, groups in split_groups.items()},
        "sample_counts": counts,
        "development_donor_dependencies": sorted(
            development_groups
            - {
                row["consultation_group_id"]
                for name in (
                    "primock57-validation-v1",
                    "primock57-smoke-v1",
                    "meddistract-detailed-v1",
                )
                for row in _manifest_rows(name, manifests[name])
            }
        ),
        "augmentation_inheritance_rule": "Every derived audio child inherits the original consultation group's split; donor contributors must share that split.",
        "rows": split_rows,
        "excluded_sources": [
            {
                "name": "primock57-full-v1",
                "reason": "rights_reviewed metadata is absent; not used in this partition",
            },
            {
                "name": "primock57-full-expansion-v1",
                "reason": "rights_reviewed metadata is absent; not used in this partition",
            },
            {
                "name": "beccsv-synthetic-dev-v1",
                "reason": "synthetic challenge cases are not licensed original consultation audio",
            },
        ],
        "limitations": [
            "Training groups have historical benchmark outputs; those outputs remain immutable but are not post-training holdout results.",
            "Group separation does not establish speaker, site, device, or upstream model-training independence.",
            "The reserved acceptance split is represented by group IDs only; its labels and audio were not read or used.",
            "References are public development labels, not adjudicated clinical gold.",
            "No training or augmentation was run by this split-generation step.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = publish_json_once(args.out, build_training_split())
    print(
        json.dumps(
            {
                "output": args.out.as_posix(),
                "sha256": _sha(args.out),
                "group_counts": report["group_counts"],
                "sample_counts": report["sample_counts"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
