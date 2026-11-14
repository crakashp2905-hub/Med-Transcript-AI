import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_support_matrix_only_claims_source_audited_combinations():
    document = (ROOT / "docs/runtime-support-matrix.md").read_text(
        encoding="utf-8"
    )
    visual = json.loads(
        (ROOT / "evaluation/reports/master-task-mta-09-20-4304b85.json").read_text(
            encoding="utf-8"
        )
    )
    audio = json.loads(
        (ROOT / "evaluation/reports/audio-filter-resource-v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert visual["runtime"]["browser"] == "Google Chrome 157.0.0.0"
    assert visual["runtime"]["playwright"] == "1.64.1"
    assert audio["environment"]["logical_cpu_count"] == 8
    assert audio["environment"]["python"] == "3.13.5"
    assert audio["summary"]["maximum_tested_duration_seconds"] < 11
    assert "TypeScript | `7.0.2`" in document
    assert "Not established" in document
    assert "not physical tablets or phones" in document
    assert "RAM capacity" in document
