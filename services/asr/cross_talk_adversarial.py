"""Replay a frozen synthetic cross-talk scenario through local tiny.en ASR."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from uuid import uuid4

from services.api.ingest import inspect_pcm_wav
from services.asr.adapter import FasterWhisperAdapter
from services.asr.profiles import load_profiles
from services.asr.transcripts import build_transcript
from services.evaluation import tokens


SCENARIO_ID = "two-speaker-overlap"
RESERVED_GROUPS = {f"day5_consultation{number:02d}" for number in (5, 6, 7)}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def build(
    root=".", output_path="evaluation/runs/asr-adversarial-cross-talk-v1/report.json"
):
    root = Path(root).resolve()
    output_path = (root / output_path).resolve()
    if not output_path.is_relative_to(root) or output_path.exists():
        raise ValueError("output_path_must_be_new_and_inside_repository")
    scenario_manifest_path = (
        root / "evaluation/scenarios/offline-encounters-v1/manifest.json"
    )
    scenario_manifest = json.loads(scenario_manifest_path.read_text(encoding="utf-8"))
    scenarios = [
        row
        for row in scenario_manifest["scenarios"]
        if row["scenario_id"] == SCENARIO_ID
    ]
    if len(scenarios) != 1:
        raise ValueError("cross_talk_scenario_not_unique")
    scenario = scenarios[0]
    if (
        scenario["source_group_id"] in RESERVED_GROUPS
        or scenario["scenario_type"] != "overlapping"
        or scenario["channels"] != 1
        or scenario["audio_transform"].get("overlap_ms", 0) <= 0
    ):
        raise ValueError("cross_talk_scenario_outside_approved_scope")
    source_manifest_path = (
        root / "evaluation/datasets/primock57-expanded-v1/manifest.json"
    )
    if (
        _sha(source_manifest_path.read_bytes())
        != scenario["source_dataset_manifest_sha256"]
    ):
        raise ValueError("cross_talk_source_manifest_hash_mismatch")
    audio_path = (
        root / "evaluation/scenarios/offline-encounters-v1" / scenario["audio_asset"]
    ).resolve()
    if not audio_path.is_relative_to(root):
        raise ValueError("cross_talk_audio_outside_repository")
    audio_bytes = audio_path.read_bytes()
    if _sha(audio_bytes) != scenario["audio_sha256"]:
        raise ValueError("cross_talk_audio_hash_mismatch")
    metadata = inspect_pcm_wav(audio_path)
    metadata["sha256"] = scenario["audio_sha256"]

    profile_file = root / "data/asr-smoke-profiles.json"
    profile = load_profiles(profile_file)["tiny-en-smoke-v1"]
    if profile.availability()["status"] != "available_not_admitted":
        raise RuntimeError("verified_local_tiny_en_profile_unavailable")
    adapter = FasterWhisperAdapter(profile)
    raw = adapter.transcribe(audio_path, metadata, checkpoint=lambda: None)
    transcript = build_transcript(
        raw,
        metadata,
        str(uuid4()),
        str(uuid4()),
        profile,
        str(uuid4()),
        1,
    )
    hypothesis = " ".join(segment["text"].strip() for segment in raw["segments"])
    reference_token_set = {
        token
        for turn in scenario["transcript_turns"]
        for token in tokens(turn["reference"])
    }
    unmatched_tokens = list(
        dict.fromkeys(
            token for token in tokens(hypothesis) if token not in reference_token_set
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_code = (
        "services/asr/cross_talk_adversarial.py",
        "services/asr/adapter.py",
        "services/asr/profiles.py",
        "services/evaluation.py",
    )
    report = {
        "schema_version": "synthetic_cross_talk_asr_replay_v1",
        "task_id": "MTA-ASR-I10",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "scenario_id": SCENARIO_ID,
        "scope": "public mock speech, developer-scripted synthetic mono overlap; no reserved or real-patient data",
        "source_group_id": scenario["source_group_id"],
        "scenario_manifest_sha256": _sha(scenario_manifest_path.read_bytes()),
        "scenario_audio_sha256": scenario["audio_sha256"],
        "scenario_audio_path": (
            Path("evaluation/scenarios/offline-encounters-v1") / scenario["audio_asset"]
        ).as_posix(),
        "source_dataset_manifest_sha256": scenario["source_dataset_manifest_sha256"],
        "source_dataset_manifest_path": "evaluation/datasets/primock57-expanded-v1/manifest.json",
        "overlap_ms": scenario["audio_transform"]["overlap_ms"],
        "reference_turns": scenario["transcript_turns"],
        "runtime": adapter.runtime_receipt(),
        "runtime_environment": adapter._runtime_environment(),
        "source_code_sha256": {
            path: _sha((root / path).read_bytes()) for path in source_code
        },
        "inference_executed": raw["inference_executed"],
        "inference_seconds": raw.get("timing", {}).get("inference_seconds"),
        "hypothesis": hypothesis,
        "reference_unmatched_hypothesis_tokens": unmatched_tokens,
        "reference_comparison": "normalized hypothesis tokens absent from the union of the two source reference turns; diagnostic only, not clinical adjudication",
        "segments": raw["segments"],
        "transcript_review_status": transcript["status"],
        "transcript_review_flags": transcript["review_flags"],
        "application_note_generation": "not_exercised_by_adapter_replay",
        "application_approval": "not_exercised_by_adapter_replay",
        "wer_status": "not_scored: simultaneous reference turns have no single ordered transcript target",
        "clinical_acceptance": False,
        "limitations": [
            "One short synthetic overlap does not represent natural cross-talk, competing speech levels, or clinical room acoustics.",
            "Reference speaker roles and turn texts come from public source annotations and are not independent adjudication.",
            "This adapter replay does not test application note generation or approval behavior.",
            "The tiny.en profile is not admitted; output is development-only and no general cross-talk safety claim is made.",
        ],
    }
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="evaluation/runs/asr-adversarial-cross-talk-v1/report.json",
    )
    args = parser.parse_args()
    report = build(output_path=args.output)
    print(
        json.dumps(
            {
                "scenario_id": report["scenario_id"],
                "inference_executed": report["inference_executed"],
                "segments": len(report["segments"]),
                "output": args.output,
            }
        )
    )


if __name__ == "__main__":
    main()
