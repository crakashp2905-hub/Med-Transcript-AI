"""Generate deterministic, source-bound audio augmentations for the training split."""

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from services.audio_provenance import file_sha256
from services.immutable_reports import publish_json_once


DEFAULT_SPLIT = Path("evaluation/runs/asr-training-splits/group-split-v1.json")
DEFAULT_OUTPUT = Path("evaluation/runs/asr-training-augmentations-v2")
BASE_SEED = 20261121
RECIPES = {
    "gain-minus3db": {"operation": "gain", "gain_db": -3.0},
    "speed-perturb-104pct": {
        "operation": "polyphase_speed_perturbation",
        "output_length_ratio_numerator": 25,
        "output_length_ratio_denominator": 26,
        "playback_speed_factor": 1.04,
        "pitch_preserving": False,
    },
    "synthetic-pink-noise-20db": {
        "operation": "synthetic_colored_noise_mix",
        "noise_kind": "pink_1_over_sqrt_frequency",
        "snr_db": 20.0,
    },
}


def _commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _seed(sample_id, transform):
    payload = f"{BASE_SEED}:{sample_id}:{transform}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _read_pcm(path):
    with wave.open(str(path), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != 16000
            or source.getcomptype() != "NONE"
        ):
            raise ValueError("training_augmentation_requires_mono_16khz_pcm16")
        frames = source.getnframes()
        raw = source.readframes(frames)
        if len(raw) != frames * 2:
            raise ValueError("training_augmentation_source_frame_count_mismatch")
    values = np.frombuffer(raw, dtype="<i2").copy()
    if values.size == 0 or not np.any(values):
        raise ValueError("training_augmentation_source_must_contain_non_silent_pcm")
    return values


def _to_pcm16(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("training_augmentation_invalid_float_pcm")
    peak = float(np.max(np.abs(values)))
    safety_gain = min(1.0, 0.98 / peak) if peak else 1.0
    scaled = values * safety_gain
    pcm = np.rint(scaled * 32768.0).clip(-32768, 32767).astype("<i2")
    return pcm, safety_gain


def apply_augmentation(pcm16, transform, seed):
    """Return derived PCM, actual parameters, and deterministic seed metadata."""
    source = np.asarray(pcm16, dtype="<i2")
    signal = source.astype(np.float64) / 32768.0
    if transform == "gain-minus3db":
        gain = 10 ** (RECIPES[transform]["gain_db"] / 20.0)
        output, safety_gain = _to_pcm16(signal * gain)
        parameters = {**RECIPES[transform], "linear_gain": gain}
    elif transform == "speed-perturb-104pct":
        ratio = RECIPES[transform]
        stretched = resample_poly(
            signal,
            ratio["output_length_ratio_numerator"],
            ratio["output_length_ratio_denominator"],
        )
        output, safety_gain = _to_pcm16(stretched)
        parameters = {
            **ratio,
            "input_frames": int(source.size),
            "output_frames": int(output.size),
            "actual_output_length_ratio": output.size / source.size,
        }
    elif transform == "synthetic-pink-noise-20db":
        recipe = RECIPES[transform]
        rng = np.random.default_rng(seed)
        white = rng.standard_normal(source.size)
        frequencies = np.fft.rfftfreq(source.size, d=1 / 16000)
        spectrum = np.fft.rfft(white)
        weights = np.zeros_like(frequencies)
        weights[1:] = 1 / np.sqrt(frequencies[1:])
        noise = np.fft.irfft(spectrum * weights, n=source.size)
        noise_rms = float(np.sqrt(np.mean(noise * noise)))
        speech_rms = float(np.sqrt(np.mean(signal * signal)))
        if noise_rms <= 0 or speech_rms <= 0:
            raise ValueError("training_augmentation_noise_or_speech_rms_invalid")
        noise *= (speech_rms / (10 ** (recipe["snr_db"] / 20.0))) / noise_rms
        mixed = signal + noise
        output, safety_gain = _to_pcm16(mixed)
        parameters = {
            **recipe,
            "measured_input_speech_rms": speech_rms,
            "target_noise_rms_before_headroom": speech_rms
            / (10 ** (recipe["snr_db"] / 20.0)),
            "post_mix_safety_gain": safety_gain,
        }
    else:
        raise ValueError("unknown_training_augmentation")
    return output, parameters, safety_gain


def _write_pcm16_once(path, pcm16):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        with wave.open(handle, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(np.asarray(pcm16, dtype="<i2").tobytes())


def generate_augmentations(split_path=DEFAULT_SPLIT, output_root=DEFAULT_OUTPUT):
    split_path, output_root = Path(split_path), Path(output_root)
    if output_root.exists():
        raise ValueError("augmentation_output_version_already_exists")
    split_bytes = split_path.read_bytes()
    split = json.loads(split_bytes)
    if (
        split.get("schema_version") != "asr_original_consultation_group_split_v1"
        or split.get("complete") is not True
        or split.get("acceptance_labels_accessed") is not False
    ):
        raise ValueError("verified_training_split_required")
    reserved = set(split.get("group_assignments", {}).get("reserved_acceptance", []))
    training_rows = [
        row for row in split.get("rows", []) if row.get("split") == "training"
    ]
    if not training_rows or any(
        set(row.get("contributing_group_ids", [])) & reserved for row in training_rows
    ):
        raise ValueError("reserved_or_empty_training_split_forbidden")
    sample_ids = [row.get("sample_id") for row in training_rows]
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("duplicate_training_sample_ids")

    prepared = []
    for row in training_rows:
        source = Path(row["source_audio_path"])
        if not source.is_file() or source.is_symlink():
            raise ValueError("local_training_source_audio_required")
        if file_sha256(source) != row["audio_sha256"]:
            raise ValueError("training_source_audio_hash_mismatch")
        pcm = _read_pcm(source)
        for transform in RECIPES:
            seed = _seed(row["sample_id"], transform)
            derived, parameters, safety_gain = apply_augmentation(pcm, transform, seed)
            prepared.append(
                {
                    "row": row,
                    "transform": transform,
                    "seed": seed,
                    "pcm": derived,
                    "parameters": parameters,
                    "safety_gain": safety_gain,
                }
            )

    output_root.mkdir(parents=True, exist_ok=False)
    output_rows = []
    for item in prepared:
        parent = item["row"]
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(parent["sample_id"]))
        relpath = Path("audio") / item["transform"] / f"{safe_id}.wav"
        target = output_root / relpath
        _write_pcm16_once(target, item["pcm"])
        output_rows.append(
            {
                "augmentation_id": f"{parent['sample_id']}::{item['transform']}",
                "source_sample_id": parent["sample_id"],
                "parent_consultation_group_id": parent["consultation_group_id"],
                "contributing_group_ids": parent["contributing_group_ids"],
                "split": parent["split"],
                "source_dataset": parent["source_dataset"],
                "parent_audio_sha256": parent["audio_sha256"],
                "augmented_audio_path": relpath.as_posix(),
                "augmented_audio_sha256": file_sha256(target),
                "reference_sha256": parent["reference_sha256"],
                "transform": item["transform"],
                "parameters": item["parameters"],
                "seed": item["seed"],
                "output_frames": int(item["pcm"].size),
                "output_sample_rate": 16000,
                "output_channels": 1,
                "output_encoding": "pcm_s16le",
                "split_inherited_from_parent_group": True,
                "label_handling": "unchanged_parent_reference_digest",
                "label_preservation_review": "not_human_adjudicated",
            }
        )

    source_versions = {
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
    }
    counts = {
        name: sum(row["transform"] == name for row in output_rows) for name in RECIPES
    }
    report = {
        "schema_version": "asr_training_augmentation_matrix_v1",
        "complete": True,
        "clinical_acceptance": False,
        "model_fit": False,
        "inference_executed": False,
        "source_commit": _commit(),
        "split_report_path": split_path.as_posix(),
        "split_report_sha256": hashlib.sha256(split_bytes).hexdigest(),
        "base_seed": BASE_SEED,
        "seed_derivation": "first_64_bits_sha256(base_seed:sample_id:transform)",
        "runtime_versions": source_versions,
        "parent_training_samples": len(training_rows),
        "parent_training_groups": len(
            set(row["consultation_group_id"] for row in training_rows)
        ),
        "augmentation_count": len(output_rows),
        "augmentation_count_by_transform": counts,
        "reserved_acceptance_groups_used": [],
        "augmentation_rows": output_rows,
        "limitations": [
            "The pink-noise track is synthetic and is not a recording from a licensed environment-noise corpus.",
            "Reference labels are inherited by digest; no human listening adjudication or ASR label-preservation evaluation was run.",
            "The time-stretch uses polyphase speed perturbation and changes pitch slightly; it is not pitch-preserving time stretching.",
            "No model was trained or evaluated with these derived files.",
        ],
    }
    publish_json_once(output_root / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = generate_augmentations(args.split, args.out)
    print(
        json.dumps(
            {
                "output": args.out.as_posix(),
                "report_sha256": file_sha256(args.out / "report.json"),
                "augmentation_count": report["augmentation_count"],
                "counts_by_transform": report["augmentation_count_by_transform"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
