import json
from pathlib import Path


def test_visual_regression_manifest_covers_required_synthetic_viewports():
    manifest = json.loads(
        Path("apps/clinician-web/visual-regression.synthetic.json").read_text()
    )
    assert manifest["fixture"] == "synthetic-demo"
    assert manifest["external_data"] is False
    assert set(manifest["viewports"]) == {"desktop", "tablet", "mobile"}
