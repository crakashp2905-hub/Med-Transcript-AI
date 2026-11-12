import json
from pathlib import Path


def test_frontend_validation_manifest_covers_required_local_suites():
    manifest = json.loads(
        Path("apps/clinician-web/validation-manifest.json").read_text()
    )
    assert manifest["typecheck"] and manifest["build"] and manifest["audit"]
    assert manifest["playwright"] == "synthetic-fixtures-only"
    assert manifest["backend_cloud_dependencies"] is False
