import json

from services.api.ingest import file_sha256
from services.conversation_errors import analyze


def test_full_consultation_word_edits_replay_per_source_group():
    root = "evaluation"
    manifest_path = f"{root}/datasets/primock57-full-v1/manifest.json"
    baseline_path = f"{root}/reports/full-consultation-omi-2026-10-25.json"
    diagnostics_path = f"{root}/reports/conversation-all-errors-2026-10-26.json"
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    baseline = json.loads(open(baseline_path, encoding="utf-8").read())
    diagnostics = json.loads(open(diagnostics_path, encoding="utf-8").read())

    assert diagnostics["manifest_sha256"] == file_sha256(manifest_path)
    assert diagnostics["inputs"][baseline_path.replace("/", "\\")] == file_sha256(
        baseline_path
    )
    references = {row["group_id"]: row for row in manifest["cases"]}
    baseline_rows = {row["id"]: row for row in baseline["cases"]}
    stored = {
        row["id"]: row
        for condition in diagnostics["conditions"]
        if condition["mode"] == "baseline_fixed30"
        for row in condition["cases"]
    }
    assert set(stored) == set(baseline_rows)
    replay_edits = replay_words = 0
    for group_id, case in baseline_rows.items():
        aligned = analyze(case, references[group_id]["reference_turns"])
        receipt = stored[group_id]
        assert receipt["reference_words"] == aligned["reference_words"]
        assert receipt["normalized_edits"] == aligned["normalized_edits"]
        assert receipt["edit_types"] == aligned["edit_types"]
        assert sum(receipt["edit_types"].values()) == case["normalized_edits"]
        replay_edits += aligned["normalized_edits"]
        replay_words += aligned["reference_words"]

    assert (replay_edits, replay_words) == (679, 5204)
