import json
import hashlib

import pytest

from services.asr.clinical_lexicon import build_lexicon


def _manifest(path, *, split="development", groups=None):
    body = {
        "dataset_id": "licensed-mock-development",
        "data_class": "approved_public",
        "rights_reviewed": True,
        "license": "CC-BY-4.0",
        "source_revision": "revision",
        "split": split,
        "cases": [
            {
                "foreground_id": group,
                "reference_turns": [
                    {
                        "reference": "Patient denies warfarin and takes 5 mg.",
                        "role": "patient",
                        "uncertain_reference": False,
                    },
                    {
                        "reference": "Possible metformin",
                        "role": "doctor",
                        "uncertain_reference": True,
                    },
                ],
            }
            for group in (groups or ["dev-consult-1"])
        ],
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    (path.parent / "lock.json").write_text(
        json.dumps({"manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}),
        encoding="utf-8",
    )
    return path


def _reservation(path, groups=None):
    path.write_text(
        json.dumps({"reserved_groups": groups or ["acceptance-consult"]}),
        encoding="utf-8",
    )
    return path


def test_lexicon_provenance_binds_exact_reference_offsets_and_excludes_uncertain(
    tmp_path,
):
    manifest = _manifest(tmp_path / "manifest.json")
    reservation = _reservation(tmp_path / "reservation.json")
    result = build_lexicon([manifest], reservation, tmp_path / "lexicon.json")
    warfarin = next(row for row in result["entries"] if row["term"] == "warfarin")
    evidence = warfarin["provenance"][0]
    assert result["acceptance_data_used"] is False
    assert result["uncertain_reference_rows_excluded"]
    assert evidence["group_id"] == "dev-consult-1"
    assert evidence["start_char"] == len("Patient denies ")
    assert evidence["end_char"] == evidence["start_char"] + len("warfarin")
    assert len(evidence["reference_sha256"]) == 64


def test_lexicon_rejects_reserved_acceptance_groups_and_acceptance_split(tmp_path):
    reservation = _reservation(tmp_path / "reservation.json")
    reserved_manifest = _manifest(
        tmp_path / "reserved.json", groups=["acceptance-consult"]
    )
    with pytest.raises(ValueError, match="reserved_acceptance_group"):
        build_lexicon(
            [reserved_manifest], reservation, tmp_path / "reserved-lexicon.json"
        )
    acceptance_manifest = _manifest(
        tmp_path / "acceptance.json", split="acceptance", groups=["other"]
    )
    with pytest.raises(ValueError, match="rights_reviewed_development_manifest"):
        build_lexicon(
            [acceptance_manifest], reservation, tmp_path / "acceptance-lexicon.json"
        )
