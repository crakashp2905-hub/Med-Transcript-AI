import json
from pathlib import Path


def test_playwright_manifest_covers_synthetic_demo_flows_without_cloud_dependencies():
    manifest = json.loads(Path('apps/clinician-web/playwright.synthetic.json').read_text())
    assert manifest['backend'] == 'synthetic-fixtures-only'
    assert manifest['cloud_dependencies'] is False
    assert set(manifest['flows']) == {'recovery', 'source-edits', 'errors', 'keyboard-only-review', 'role-correction', 'local-demo'}
