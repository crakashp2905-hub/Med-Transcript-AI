import hashlib
import json
from pathlib import Path


REPORT_PATH = Path(
    "evaluation/runs/meddistract-detailed-v7/correction-tables/"
    "tiny-en-grouped-confusion-table-v1.json"
)
REPORT_SHA256 = "aa667aeec85add08cc9c1277d4ed5d95b24b8e583484d928586eaca9f5dbe717"
SOURCE_RECEIPT_SHA256 = (
    "06da69961c07be44c3de5c72f799a78d031b0748a1231931e483eee0ae7ef6cd"
)


def test_grouped_confusion_table_is_hash_bound_and_excludes_reserved_groups():
    raw = REPORT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    assert report["schema_version"] == "asr_grouped_correction_confusion_table_v1"
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["automatic_promotion"] is False
    assert report["model_fit"] is False
    assert report["inference_executed"] is False
    assert report["source_commit"] == "368e05c77887802f9844ca53c29a1ae740e4c11d"
    source_path = Path(report["inputs"]["receipt_path"])
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == SOURCE_RECEIPT_SHA256
    assert report["inputs"]["receipt_sha256"] == SOURCE_RECEIPT_SHA256
    assert report["summary"] == {
        "case_count": 16,
        "consultation_group_count": 8,
        "reference_words": 27366,
        "normalized_edits": 9104,
        "substitutions": 4008,
        "deletions": 3878,
        "insertions": 1218,
        "confusion_rows": 9104,
        "failed_cases": 0,
        "wer": 9104 / 27366,
    }
    protocol = report["split_protocol"]
    assert protocol["method"] == "leave_one_foreground_consultation_group_out"
    assert protocol["reserved_acceptance_groups_used"] == []
    for group, fold in protocol["folds"].items():
        assert fold["held_out_group"] == group
        assert group not in fold["training_groups"]
        assert set(fold["training_groups"]) == set(protocol["consultation_groups"]) - {
            group
        }
    assert len(report["training_table"]) == 9104
    assert all(
        not row["consultation_group"].startswith("day5_consultation0")
        for row in report["training_table"]
    )
