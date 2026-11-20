import hashlib
import json
from pathlib import Path

from services.asr.cross_talk_adversarial import RESERVED_GROUPS, SCENARIO_ID


ROOT = Path(__file__).resolve().parents[1]


def test_cross_talk_challenge_is_source_bound_and_nonreserved():
    scenario_path = ROOT / "evaluation/scenarios/offline-encounters-v1/manifest.json"
    manifest = json.loads(scenario_path.read_text(encoding="utf-8"))
    rows = [row for row in manifest["scenarios"] if row["scenario_id"] == SCENARIO_ID]
    assert len(rows) == 1
    scenario = rows[0]
    assert scenario["scenario_type"] == "overlapping"
    assert scenario["source_group_id"] not in RESERVED_GROUPS
    assert scenario["channels"] == 1
    assert scenario["audio_transform"]["overlap_ms"] > 0
    assert len(scenario["transcript_turns"]) == 2
    first, second = scenario["transcript_turns"]
    assert max(first["start_ms"], second["start_ms"]) < min(
        first["end_ms"], second["end_ms"]
    )
    audio = (
        ROOT / "evaluation/scenarios/offline-encounters-v1" / scenario["audio_asset"]
    )
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == scenario["audio_sha256"]
    source_manifest = ROOT / "evaluation/datasets/primock57-expanded-v1/manifest.json"
    assert (
        hashlib.sha256(source_manifest.read_bytes()).hexdigest()
        == scenario["source_dataset_manifest_sha256"]
    )
