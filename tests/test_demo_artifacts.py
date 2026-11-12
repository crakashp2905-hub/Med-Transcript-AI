import json
from pathlib import Path


def test_demo_artifacts_are_local_synthetic_and_cover_screenshots():
    manifest = json.loads(Path("docs/demo-artifacts.json").read_text())
    assert manifest["source"] == "synthetic-local-fixtures"
    assert manifest["external_input"] is False and manifest["patient_data"] is False
    assert set(manifest["screenshots"]) == {"desktop", "tablet", "mobile"}
