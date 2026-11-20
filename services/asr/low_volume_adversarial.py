"""Run a source-bound, exploratory low-volume patient-denial replay."""

import argparse
import hashlib
import json
import math
import subprocess
import wave
from pathlib import Path

from services.api.ingest import inspect_pcm_wav
from services.asr.adapter import FasterWhisperAdapter
from services.asr.profiles import load_profiles
from services.evaluation import score


SAMPLE_ID = "day1_consultation09_patient.utterance03"
ATTENUATION_DB = (0, -12, -20)
RESERVED_GROUPS = {f"day5_consultation{number:02d}" for number in (5, 6, 7)}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _attenuate_wav(source_bytes, level_db):
    if level_db > 0 or not math.isfinite(level_db):
        raise ValueError("attenuation_must_be_finite_nonpositive_db")
    import numpy as np

    with wave.open(__import__("io").BytesIO(source_bytes), "rb") as audio:
        params = audio.getparams()
        if (params.nchannels, params.sampwidth, params.framerate) != (1, 2, 16000):
            raise ValueError("expected_mono_16khz_pcm16")
        raw = audio.readframes(params.nframes)
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    gain = 10 ** (level_db / 20)
    attenuated = np.rint(samples * gain).clip(-32768, 32767).astype("<i2")
    import io

    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(attenuated.tobytes())
    return output.getvalue()


def _tokens(text):
    return text.lower().replace(",", " ").replace(".", " ").split()


def build(root=".", output_dir="evaluation/runs/asr-adversarial-low-volume-v1"):
    root = Path(root).resolve()
    output_dir = (root / output_dir).resolve()
    if not output_dir.is_relative_to(root) or output_dir.exists():
        raise ValueError("output_path_must_be_new_and_inside_repository")
    manifest_path = root / "evaluation/datasets/primock57-expanded-v1/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [row for row in manifest["samples"] if row["sample_id"] == SAMPLE_ID]
    if len(rows) != 1:
        raise ValueError("adversarial_sample_not_unique")
    row = rows[0]
    if row["group_id"] in RESERVED_GROUPS or row["speaker_role"] != "patient":
        raise ValueError("adversarial_sample_outside_approved_development_scope")
    source_path = root / "evaluation/datasets/primock57-expanded-v1" / row["audio"]
    source_bytes = source_path.read_bytes()
    if _sha(source_bytes) != row["audio_sha256"]:
        raise ValueError("adversarial_source_hash_mismatch")
    source_metadata = inspect_pcm_wav(source_path)
    profile_file = root / "data/asr-smoke-profiles.json"
    profile = load_profiles(profile_file)["tiny-en-smoke-v1"]
    if profile.availability()["status"] != "available_not_admitted":
        raise RuntimeError("verified_local_tiny_en_profile_unavailable")

    output_dir.mkdir(parents=True)
    adapter = FasterWhisperAdapter(profile)
    conditions = []
    for level_db in ATTENUATION_DB:
        audio_bytes = (
            source_bytes if level_db == 0 else _attenuate_wav(source_bytes, level_db)
        )
        wav_path = output_dir / f"patient_denial_{level_db}db.wav"
        wav_path.write_bytes(audio_bytes)
        metadata = inspect_pcm_wav(wav_path)
        metadata.update({"sha256": _sha(audio_bytes)})
        raw = adapter.transcribe(wav_path, metadata, checkpoint=lambda: None)
        text = " ".join(segment["text"].strip() for segment in raw["segments"])
        metrics = score(row["reference"], text, include_extended=True)
        reference_tokens = set(_tokens(row["reference"])) & {"no", "not"}
        hypothesis_tokens = set(_tokens(text))
        import numpy as np

        with wave.open(str(wav_path), "rb") as audio:
            pcm = np.frombuffer(audio.readframes(metadata["frames"]), dtype="<i2")
        conditions.append(
            {
                "attenuation_db": level_db,
                "audio_path": wav_path.relative_to(root).as_posix(),
                "audio_sha256": _sha(audio_bytes),
                "peak_absolute_pcm": int(np.max(np.abs(pcm.astype(np.int32)))),
                "inference_executed": raw["inference_executed"],
                "inference_seconds": raw.get("timing", {}).get("inference_seconds"),
                "hypothesis": text,
                "metrics": metrics,
                "reference_negation_tokens": sorted(reference_tokens),
                "retained_reference_negation_tokens": sorted(
                    reference_tokens & hypothesis_tokens
                ),
                "segments": raw["segments"],
            }
        )

    source_files = [
        "services/asr/low_volume_adversarial.py",
        "services/asr/adapter.py",
        "services/asr/profiles.py",
        "services/evaluation.py",
    ]
    code_hashes = {path: _sha((root / path).read_bytes()) for path in source_files}
    report = {
        "schema_version": "low_volume_patient_denial_replay_v1",
        "task_id": "MTA-ASR-I10",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "scope": "one public mock patient utterance from the nonreserved development split",
        "data_class": manifest["data_class"],
        "dataset_manifest_sha256": _sha(manifest_path.read_bytes()),
        "sample_id": SAMPLE_ID,
        "group_id": row["group_id"],
        "speaker_role": row["speaker_role"],
        "reference": row["reference"],
        "source_audio_sha256": row["audio_sha256"],
        "source_audio_metadata": source_metadata,
        "attack": {
            "type": "uniform_linear_pcm_attenuation",
            "attenuation_db": list(ATTENUATION_DB),
            "reference_is_original": True,
            "parameters_predeclared_in_runner": True,
            "inference_repeated_for_each_condition": True,
        },
        "runtime": adapter.runtime_receipt(),
        "runtime_environment": adapter._runtime_environment(),
        "source_code_sha256": code_hashes,
        "conditions": conditions,
        "wer_gate": {
            "maximum": 0.05,
            "admission": "not_claimed_for_this_single_case",
            "primary_gate_modified": False,
        },
        "clinical_acceptance": False,
        "real_patient_processing_authorized": False,
        "limitations": [
            "One convenience-selected public mock utterance is not a representative low-volume denial challenge set.",
            "Attenuation is a digital amplitude transform, not a calibrated acoustic recording condition.",
            "The local tiny.en profile is not admitted and a single example cannot establish a no-hallucination guarantee.",
            "This replay does not test deceptive spoken prompts, cross-talk, or auto-approval behavior.",
        ],
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", default="evaluation/runs/asr-adversarial-low-volume-v1"
    )
    args = parser.parse_args()
    report = build(output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": args.output_dir,
                "conditions": len(report["conditions"]),
                "inference_executed": all(
                    condition["inference_executed"]
                    for condition in report["conditions"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
