import hashlib
import json
from pathlib import Path


REPORT = Path("evaluation/reports/asr-training-resource-audit-v1.json")
REPORT_SHA256 = "c692ff374f2dcdefcd4ee5d3969e9b3781b77c92e11f05e2234ebebf73edea0b"


def test_training_resource_audit_records_missing_local_training_capability():
    raw = REPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    assert report["schema_version"] == "asr_training_resource_audit_v1"
    assert report["source_commit"] == "d56878c3066400dd0b8ca680c7648bb1ae2cdbbd"
    assert report["decision"] == "BLOCKED_MISSING_RESOURCE"
    assert report["automatic_download"] is False
    assert report["model_fit"] is False
    assert report["inference_executed"] is False
    assert report["training_runtime"]["torch_version"] == "2.13.0+cpu"
    assert report["training_runtime"]["cuda_available"] is False
    assert report["training_runtime"]["cuda_device_count"] == 0
    assert report["training_runtime"]["modules_available"] == {
        "transformers": True,
        "peft": False,
        "accelerate": False,
        "datasets": False,
        "bitsandbytes": False,
    }
    assert (
        report["repository_model_evidence"][
            "approved_trainable_architecture_or_checkpoint_identified"
        ]
        is False
    )
    assert report["repository_model_evidence"]["optimizer_recipe_identified"] is False

    progress_raw = (
        Path("docs/asr-rnd-progress.md").read_text(encoding="utf-8").encode("utf-8")
    )
    ledger = json.loads(Path("evaluation/asr-task-ledger-v5.json").read_text())
    assert (
        ledger["progress_record"]["sha256"] == hashlib.sha256(progress_raw).hexdigest()
    )
    task = next(task for task in ledger["tasks"] if task["id"] == "MTA-ASR-H06")
    assert task["status"] == "BLOCKED_MISSING_RESOURCE"
    assert task["completion_claim"] is False
