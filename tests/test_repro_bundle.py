import pytest

from services.repro_bundle import build
from services.repro_bundle import main


def test_repro_bundle_has_hashes_commands_and_negative_results():
    value = build(".")
    assert (
        value["model_free"]
        and value["downloads_attempted"] == 0
        and value["paid_calls"] == 0
    )
    assert value["negative_results_preserved"] and len(value["artifacts"]) >= 5
    assert value["clinical_release"] == "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED"
    assert value["source_commit"] and value["source_code_sha256"]
    assert value["datasets"] and all(
        row["manifest_sha256"] for row in value["datasets"]
    )
    assert value["limitations"] and any(
        "independent clinical" in item for item in value["limitations"]
    )
    assert any("benchmark_ranking" in command for command in value["commands"])
    paths = {item["path"] for item in value["artifacts"]}
    assert "evaluation/runs/primock57-smoke-v1/faster-whisper-large-v3.json" in paths


def test_repro_bundle_cli_writes_once_and_includes_provenance(tmp_path, monkeypatch):
    import json
    import sys
    from pathlib import Path

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    output = tmp_path / "pack.json"
    monkeypatch.setattr(sys, "argv", ["repro_bundle", "--output", str(output)])
    main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source_commit"]
    assert payload["datasets"]
    with pytest.raises(FileExistsError):
        main()
