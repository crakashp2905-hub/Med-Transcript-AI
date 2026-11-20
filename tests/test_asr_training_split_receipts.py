import hashlib
import json
from pathlib import Path


REPORT = Path("evaluation/runs/asr-training-splits/group-split-v1.json")
REPORT_SHA256 = "79238bbca18bc009fc3315911dcf6560c907658428cc84abe3f20e51e0842159"


def test_group_split_receipt_is_disjoint_and_keeps_acceptance_data_out():
    raw = REPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    assert report["schema_version"] == "asr_original_consultation_group_split_v1"
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["acceptance_labels_accessed"] is False
    assert report["inference_executed"] is False
    assert report["audio_transformed"] is False
    assert report["source_commit"] == "ccc9e5b668542e54508336a903f136ff6d166510"
    assert report["group_counts"] == {
        "development": 15,
        "reserved_acceptance": 3,
        "training": 16,
    }
    assert report["sample_counts"] == {"development": 76, "training": 94}
    assignments = report["group_assignments"]
    training = set(assignments["training"])
    development = set(assignments["development"])
    reserved = set(assignments["reserved_acceptance"])
    split_by_group = {
        group: split for split, groups in assignments.items() for group in groups
    }
    assert not (training & development or training & reserved or development & reserved)
    assert reserved == {
        "day5_consultation05",
        "day5_consultation06",
        "day5_consultation07",
    }
    assert all(row["split"] != "reserved_acceptance" for row in report["rows"])
    assert len(report["rows"]) == 170
    for row in report["rows"]:
        assert row["parent_group_split_inherited"] is True
        assert all(
            split_by_group[group] == row["split"]
            for group in row["contributing_group_ids"]
        )
        assert "reference" not in row
        assert len(row["reference_sha256"]) == 64
    training_hashes = {
        row["audio_sha256"] for row in report["rows"] if row["split"] == "training"
    }
    development_hashes = {
        row["audio_sha256"] for row in report["rows"] if row["split"] == "development"
    }
    assert training_hashes.isdisjoint(development_hashes)
    assert all(
        source["license"] == "CC-BY-4.0" for source in report["manifest_sources"]
    )
