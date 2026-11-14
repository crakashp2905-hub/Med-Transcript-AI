"""Build deterministic, offline product-workflow scenarios from local public clips."""

import hashlib
import json
import math
import struct
import wave
import argparse
from array import array
from pathlib import Path


SOURCE_MANIFEST = "evaluation/datasets/primock57-expanded-v1/manifest.json"
SCENARIO_SCHEMA = "offline_product_scenarios_v1"
SAMPLE_RATE = 16000
GAP_MS = 300


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_samples(root):
    manifest_path = Path(root) / SOURCE_MANIFEST
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    samples = {item["sample_id"]: item for item in manifest["samples"]}
    if len(samples) != len(manifest["samples"]):
        raise ValueError("scenario_source_sample_ids_not_unique")
    return manifest, hashlib.sha256(manifest_bytes).hexdigest(), samples


def _read_sample(root, sample):
    path = Path(root) / "evaluation/datasets/primock57-expanded-v1" / sample["audio"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sample["audio_sha256"]:
        raise ValueError("scenario_source_audio_hash_mismatch")
    with wave.open(str(path), "rb") as audio:
        if (
            audio.getframerate() != SAMPLE_RATE
            or audio.getnchannels() != 1
            or audio.getsampwidth() != 2
            or audio.getcomptype() != "NONE"
        ):
            raise ValueError("scenario_source_audio_format_unsupported")
        frames = array("h")
        frames.frombytes(audio.readframes(audio.getnframes()))
    if struct.pack("=h", 1) != struct.pack("<h", 1):
        frames.byteswap()
    return frames


def _write_wave(path, frames, channels):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        payload = array("h", frames)
        if struct.pack("=h", 1) != struct.pack("<h", 1):
            payload.byteswap()
        audio.writeframes(payload.tobytes())
    return {
        "path": path,
        "sha256": _sha256(path),
        "duration_ms": len(frames) * 1000 // (SAMPLE_RATE * channels),
        "channels": channels,
    }


def _append_turns(root, samples, sample_ids, *, stereo=False):
    channels = 2 if stereo else 1
    frames = array("h")
    turns = []
    gap = SAMPLE_RATE * GAP_MS // 1000
    for sample_id in sample_ids:
        sample = samples[sample_id]
        source = _read_sample(root, sample)
        start = len(frames) // channels
        for index, value in enumerate(source):
            if stereo:
                frames.extend(
                    (value, 0) if sample["speaker_role"] == "doctor" else (0, value)
                )
            else:
                frames.append(value)
        turns.append(
            {
                "start_ms": start * 1000 // SAMPLE_RATE,
                "end_ms": (start + len(source)) * 1000 // SAMPLE_RATE,
                "speaker_role_reference": sample["speaker_role"],
                "reference": sample["reference"],
                "source_sample_id": sample_id,
                "source_audio_sha256": sample["audio_sha256"],
            }
        )
        frames.extend([0] * (gap * channels))
    return frames, turns, channels


def _add_white_noise(signal, *, snr_db, seed):
    energy = sum(value * value for value in signal)
    signal_rms = math.sqrt(energy / len(signal)) if signal else 0.0
    if not signal_rms:
        raise ValueError("scenario_noise_requires_non_silent_audio")
    state = seed & 0xFFFFFFFF
    white = []
    for _ in signal:
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        white.append(((state / 0xFFFFFFFF) * 2.0) - 1.0)
    white_mean = sum(white) / len(white)
    white = [value - white_mean for value in white]
    white_rms = math.sqrt(sum(value * value for value in white) / len(white))
    noise_scale = signal_rms / (10 ** (snr_db / 20) * white_rms)
    noisy = array(
        "h",
        (
            max(-32768, min(32767, round(value + noise * noise_scale)))
            for value, noise in zip(signal, white)
        ),
    )
    return noisy, {
        "method": "lcg_uniform_demeaned_white_noise_v1",
        "seed": seed,
        "target_snr_db": snr_db,
        "realized_snr_db_before_pcm_clipping": round(
            20 * math.log10(signal_rms / (white_rms * noise_scale)), 6
        ),
    }


def _mix_overlap(root, samples, placements):
    segments = []
    total = 0
    for sample_id, offset_ms in placements:
        sample = samples[sample_id]
        source = _read_sample(root, sample)
        start = offset_ms * SAMPLE_RATE // 1000
        segments.append((start, source, sample))
        total = max(total, start + len(source))
    output = [0.0] * total
    turns = []
    for start, source, sample in segments:
        for index, value in enumerate(source):
            output[start + index] += value
        turns.append(
            {
                "start_ms": start * 1000 // SAMPLE_RATE,
                "end_ms": (start + len(source)) * 1000 // SAMPLE_RATE,
                "speaker_role_reference": sample["speaker_role"],
                "reference": sample["reference"],
                "source_sample_id": sample["sample_id"],
                "source_audio_sha256": sample["audio_sha256"],
            }
        )
    frames = array("h", (max(-32768, min(32767, round(value))) for value in output))
    overlap_ms = max(
        0,
        min(turns[0]["end_ms"], turns[1]["end_ms"])
        - max(turns[0]["start_ms"], turns[1]["start_ms"]),
    )
    return frames, turns, overlap_ms


def _synthetic_medication_script():
    return {
        "input_mode": "typed_synthetic_script_no_audio",
        "turns": [
            {
                "speaker_role_reference": "clinician",
                "text": "Please tell me the medicines you currently take and how you take them.",
            },
            {
                "speaker_role_reference": "patient",
                "text": "I take metformin 500 mg twice daily and lisinopril 10 mg each morning. I sometimes miss the evening metformin dose.",
            },
            {
                "speaker_role_reference": "clinician",
                "text": "Any medication allergies or reactions?",
            },
            {
                "speaker_role_reference": "patient",
                "text": "Amoxicillin gave me a rash. I have never had breathing trouble from it. I am not taking warfarin.",
            },
            {
                "speaker_role_reference": "clinician",
                "text": "I will record those details for review. I am not changing or prescribing any medication in this scenario.",
            },
        ],
        "review_targets": [
            "Bind dose and frequency to metformin, not lisinopril.",
            "Preserve the amoxicillin rash and the explicit absence of breathing trouble.",
            "Preserve the negated warfarin statement.",
            "Keep current medication history separate from a medication order.",
        ],
    }


def build_scenarios(root=".", output_dir="evaluation/scenarios/offline-encounters-v1"):
    """Regenerate scenarios using only checked-in local PriMock57 utterance clips."""
    root = Path(root)
    output_dir = Path(output_dir)
    source_manifest, source_manifest_sha, samples = _load_samples(root)
    expected_license = "CC-BY-4.0"
    if source_manifest.get("license_id") != expected_license:
        raise ValueError("scenario_source_license_unexpected")

    definitions = [
        {
            "scenario_id": "short-two-speaker-consultation",
            "scenario_type": "short",
            "group_id": "day2_consultation01",
            "sample_ids": sorted(
                [key for key in samples if key.startswith("day2_consultation01_")],
                key=lambda key: (
                    samples[key]["source_start_seconds"],
                    key,
                ),
            ),
            "mode": "sequence_mono",
            "goal": "Review a short source, inspect the transcript and complete a simulated note correction.",
        },
        {
            "scenario_id": "deterministic-background-noise",
            "scenario_type": "noisy",
            "group_id": "day1_consultation07",
            "sample_ids": sorted(
                [key for key in samples if key.startswith("day1_consultation07_")],
                key=lambda key: (
                    samples[key]["source_start_seconds"],
                    key,
                ),
            ),
            "mode": "sequence_mono_noise",
            "noise": {"target_snr_db": 12, "seed": 160101},
            "goal": "Review a noisy synthetic derivative; every transcript error remains in the fixture and is not a model score.",
        },
        {
            "scenario_id": "two-speaker-overlap",
            "scenario_type": "overlapping",
            "group_id": "day1_consultation08",
            "placements": [
                ["day1_consultation08_doctor.utterance03", 0],
                ["day1_consultation08_patient.utterance03", 2000],
            ],
            "mode": "mix_mono_overlap",
            "goal": "Review a two-voice synthetic overlap and verify that both source spans remain represented.",
        },
        {
            "scenario_id": "medication-history-script",
            "scenario_type": "medication_heavy",
            "group_id": None,
            "mode": "typed_script_only",
            "goal": "Exercise dose, frequency, allergy-reaction, negation and order-versus-history corrections without audio or inference.",
        },
        {
            "scenario_id": "two-channel-multi-speaker",
            "scenario_type": "multi_speaker",
            "group_id": "day3_consultation04",
            "sample_ids": sorted(
                [key for key in samples if key.startswith("day3_consultation04_")],
                key=lambda key: (
                    samples[key]["source_start_seconds"],
                    key,
                ),
            ),
            "mode": "sequence_stereo_by_reference_role",
            "goal": "Navigate two source channels while keeping source reference roles separate from predicted speaker roles.",
        },
    ]

    scenarios = []
    for definition in definitions:
        scenario = {
            "scenario_id": definition["scenario_id"],
            "scenario_type": definition["scenario_type"],
            "goal": definition["goal"],
            "scenario_authorship": "developer_scripted_product_workflow",
            "source_data_class": (
                "developer_authored_synthetic_text"
                if definition["mode"] == "typed_script_only"
                else "approved_public_mock_speech"
            ),
            "source_dataset": (
                None
                if definition["mode"] == "typed_script_only"
                else "primock57-20consultations-120clips-v1"
            ),
            "source_dataset_manifest_sha256": (
                None
                if definition["mode"] == "typed_script_only"
                else source_manifest_sha
            ),
            "source_group_id": definition["group_id"],
            "source_license": (
                None if definition["mode"] == "typed_script_only" else expected_license
            ),
            "speaker_roles_are_reference_only": True,
            "clinical_acceptance": False,
            "clinical_release_authorized": False,
        }
        if definition["mode"] == "typed_script_only":
            scenario["input_mode"] = "typed_synthetic_script_no_audio"
            scenario["synthetic_script"] = _synthetic_medication_script()
        else:
            if not definition.get("sample_ids") and not definition.get("placements"):
                raise ValueError("scenario_source_samples_missing")
            output_name = f"{definition['scenario_id']}.wav"
            if definition["mode"] in {"sequence_mono", "sequence_mono_noise"}:
                frames, turns, channels = _append_turns(
                    root, samples, definition["sample_ids"]
                )
                audio_transform = {"method": "sequential_public_clip_composition_v1"}
                if definition["mode"] == "sequence_mono_noise":
                    frames, noise = _add_white_noise(
                        frames,
                        snr_db=definition["noise"]["target_snr_db"],
                        seed=definition["noise"]["seed"],
                    )
                    audio_transform.update(noise)
                scenario["transcript_turns"] = turns
            elif definition["mode"] == "mix_mono_overlap":
                frames, turns, overlap_ms = _mix_overlap(
                    root, samples, definition["placements"]
                )
                channels = 1
                audio_transform = {
                    "method": "two_public_utterances_summed_with_synthetic_offset_v1",
                    "overlap_ms": overlap_ms,
                }
                scenario["transcript_turns"] = turns
            else:
                frames, turns, channels = _append_turns(
                    root, samples, definition["sample_ids"], stereo=True
                )
                audio_transform = {
                    "method": "sequential_public_clips_routed_to_stereo_channels_v1",
                    "channel_roles": {
                        "0": "doctor_reference",
                        "1": "patient_reference",
                    },
                }
                scenario["transcript_turns"] = turns
            audio = _write_wave(output_dir / "assets" / output_name, frames, channels)
            scenario["audio_asset"] = f"assets/{output_name}"
            scenario["audio_sha256"] = audio["sha256"]
            scenario["duration_ms"] = audio["duration_ms"]
            scenario["channels"] = audio["channels"]
            scenario["audio_transform"] = audio_transform
            scenario["inference_executed"] = False
        scenarios.append(scenario)

    document = {
        "schema_version": SCENARIO_SCHEMA,
        "scenario_set_id": "offline-encounters-v1",
        "generated_from_local_assets_only": True,
        "source_manifest_sha256": source_manifest_sha,
        "source_license": expected_license,
        "attribution": source_manifest["attribution"],
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "limitations": [
            "Audio scenarios are developer-composed derivatives of public mock utterance clips; the source speech is not newly recorded synthetic speech.",
            "The medication-heavy case is developer-authored text only and has no audio or ASR result.",
            "Reference speaker roles come from upstream annotations and are not diarization predictions.",
            "This scenario set is for scripted product workflow coverage, not clinical acceptance or model accuracy scoring.",
        ],
        "clinical_acceptance": False,
        "clinical_release_authorized": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return document


def main():
    parser = argparse.ArgumentParser(
        description="Build local scripted product scenarios from checked-in public clips."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--output-dir", default="evaluation/scenarios/offline-encounters-v1"
    )
    args = parser.parse_args()
    document = build_scenarios(args.root, args.output_dir)
    print(
        json.dumps(
            {
                "scenario_set_id": document["scenario_set_id"],
                "scenario_count": document["scenario_count"],
                "source_manifest_sha256": document["source_manifest_sha256"],
                "scenarios": [
                    {
                        "scenario_id": scenario["scenario_id"],
                        "scenario_type": scenario["scenario_type"],
                        "audio_asset": scenario.get("audio_asset"),
                        "audio_sha256": scenario.get("audio_sha256"),
                    }
                    for scenario in document["scenarios"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
