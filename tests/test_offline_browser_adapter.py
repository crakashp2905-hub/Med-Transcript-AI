import json
from pathlib import Path

from tests.offline_browser_server import ScriptedAdapter


def test_scripted_browser_adapter_uses_local_public_reference_without_claiming_inference():
    manifest = json.loads(
        Path("evaluation/datasets/primock57-smoke-v1/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    sample = next(
        item
        for item in manifest["samples"]
        if item["sample_id"] == "day1_consultation01_patient.utterance03"
    )
    result = ScriptedAdapter(None).transcribe(
        Path(sample["audio"]), {"duration_ms": 9000}, lambda: None
    )

    assert result["inference_executed"] is False
    assert result["segments"][0]["text"] == sample["reference"]
    assert result["runtime_packages"] == {"fixture": "scripted_non_asr_v1"}
