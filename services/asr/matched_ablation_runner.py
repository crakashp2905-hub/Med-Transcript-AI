"""Run a six-arm, same-input ASR ablation using one pinned local model."""

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import time
import wave

from services.api.ingest import file_sha256
from services.asr.ablation import ARM_COMPONENTS, summarize_matched_ablation
from services.asr.context_biasing import build_context_bias
from services.asr.energy_vad_chunking import energy_vad_windows
from services.asr.profiles import load_profiles
from services.evidence_io import atomic_json
from services.evaluation import score
from services.immutable_reports import publish_json_once

ARM_IDS = (
    "fixed_baseline",
    "vad_only",
    "decoder_only",
    "terminology_only",
    "repair_only",
    "full_pipeline",
)
REPAIR_RISK = re.compile(
    r"\b(?:\d+(?:\.\d+)?|mg|mcg|g|ml|units?|daily|twice|once|no|not|denies|"
    r"allerg\w*|amoxicillin|lisinopril|metformin|paracetamol|warfarin)\b",
    re.IGNORECASE,
)
MAX_REPAIRS_PER_CASE = 12
REPAIR_PADDING_FRAMES = 4000
ENERGY_VAD_CONFIG = {
    "candidate_id": "energy_vad_boundary_v1",
    "sample_rate": 16000,
    "frame_ms": 20,
    "target_seconds": 30,
    "search_seconds": 5,
    "minimum_silence_ms": 200,
    "overlap_seconds": 0,
    "threshold_dbfs": -38.0,
}


def _reference(case):
    return " ".join(
        re.sub(r"<[^>]+>", "", turn["reference"]) for turn in case["reference_turns"]
    )


def _read_source(path, expected_sha256):
    if file_sha256(path) != expected_sha256:
        raise ValueError("ablation_source_audio_hash_mismatch")
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (
            1,
            16000,
            2,
        ):
            raise ValueError("ablation_source_must_be_mono_16khz_pcm16")
        pcm = audio.readframes(audio.getnframes())
    return pcm


def _decode(model, pcm, start_frame, end_frame, *, beam_size, hotwords=None):
    import numpy as np

    samples = np.frombuffer(pcm[start_frame * 2 : end_frame * 2], dtype="<i2")
    if not len(samples):
        raise ValueError("ablation_empty_decode_crop")
    options = {
        "language": "en",
        "task": "transcribe",
        "beam_size": beam_size,
        "temperature": 0.0,
        "vad_filter": False,
        "word_timestamps": False,
        "condition_on_previous_text": False,
        "log_progress": False,
    }
    if hotwords:
        options["hotwords"] = hotwords
    segments, _ = model.transcribe(samples.astype(np.float32) / 32768.0, **options)
    crop_frames = end_frame - start_frame
    result = []
    for segment in segments:
        if (
            not isinstance(segment.text, str)
            or not math.isfinite(segment.start)
            or not math.isfinite(segment.end)
            or segment.start < 0
            or segment.end < segment.start
            or segment.start > crop_frames / 16000 + 1.0
        ):
            raise ValueError("invalid_ablation_decoder_segment")
        bounded_start = min(crop_frames, round(segment.start * 16000))
        bounded_end = min(crop_frames, round(segment.end * 16000))
        result.append(
            {
                "start_frame": start_frame + bounded_start,
                "end_frame": start_frame + max(bounded_start, bounded_end),
                "text": segment.text.strip(),
            }
        )
    return result


def _risk_repair(model, pcm, segments, *, beam_size):
    risk_segments = [
        segment for segment in segments if REPAIR_RISK.search(segment["text"])
    ]
    selected = risk_segments[:MAX_REPAIRS_PER_CASE]
    replaced = []
    for segment in selected:
        start = max(0, segment["start_frame"] - REPAIR_PADDING_FRAMES)
        end = min(len(pcm) // 2, segment["end_frame"] + REPAIR_PADDING_FRAMES)
        candidate = _decode(model, pcm, start, end, beam_size=beam_size)
        replaced.append(
            {
                "source_interval_frames": [start, end],
                "reason": "fixed_lexical_risk_pattern_v1",
                "candidate_text": " ".join(row["text"] for row in candidate),
                "review_required": True,
                "adopted": False,
            }
        )
        segment["text"] = " ".join(row["text"] for row in candidate)
    return replaced, max(0, len(risk_segments) - len(selected))


def _run_case(model, case, audio_path, arm_id, beam_size, hotwords, vad_profile):
    started = time.perf_counter()
    pcm = _read_source(audio_path, case["audio_sha256"])
    total_frames = len(pcm) // 2
    if arm_id in {"vad_only", "full_pipeline"}:
        spans = energy_vad_windows(
            pcm,
            sample_rate=vad_profile["sample_rate"],
            frame_ms=vad_profile["frame_ms"],
            target_seconds=vad_profile["target_seconds"],
            search_seconds=vad_profile["search_seconds"],
            minimum_silence_ms=vad_profile["minimum_silence_ms"],
            overlap_seconds=vad_profile["overlap_seconds"],
            threshold_dbfs=vad_profile["threshold_dbfs"],
        )
    else:
        spans = [(0, total_frames)]

    if not spans:
        segments = []
        vad_missed_all = arm_id in {"vad_only", "full_pipeline"}
    else:
        vad_missed_all = False
        segments = []
        for start, end in spans:
            segments.extend(
                _decode(
                    model,
                    pcm,
                    start,
                    end,
                    beam_size=beam_size,
                    hotwords=hotwords,
                )
            )

    repairs, skipped_repairs = [], 0
    if arm_id in {"repair_only", "full_pipeline"} and segments:
        repairs, skipped_repairs = _risk_repair(
            model, pcm, segments, beam_size=beam_size
        )
    hypothesis = " ".join(segment["text"] for segment in segments).strip()
    return {
        "group_id": case["group_id"],
        "audio_sha256": case["audio_sha256"],
        "reference_sha256": hashlib.sha256(
            _reference(case).encode("utf-8")
        ).hexdigest(),
        "condition": case["condition"],
        "foreground_id": case["foreground_id"],
        "donor_id": case.get("donor_id"),
        "hypothesis": hypothesis,
        "failed": False,
        "vad_interval_count": len(spans)
        if arm_id in {"vad_only", "full_pipeline"}
        else None,
        "vad_missed_all_speech": vad_missed_all,
        "repair_candidates": repairs,
        "skipped_risk_repairs_due_to_bound": skipped_repairs,
        "wall_seconds": time.perf_counter() - started,
    }


def _profile_and_manifest(suite_path, profile_file, profile_id):
    suite_path = Path(suite_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest_path = Path(suite["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if file_sha256(manifest_path) != suite["manifest_sha256"]:
        raise ValueError("ablation_manifest_hash_mismatch")
    lock_path = manifest_path.parent / "lock.json"
    if (
        json.loads(lock_path.read_text(encoding="utf-8"))["manifest_sha256"]
        != suite["manifest_sha256"]
    ):
        raise ValueError("ablation_manifest_lock_mismatch")
    reservation = json.loads(
        Path("evaluation/acceptance-reservation-v1.json").read_text(encoding="utf-8")
    )
    reserved = set(reservation["reserved_groups"])
    if any(
        case["foreground_id"] in reserved or case.get("donor_id") in reserved
        for case in manifest["cases"]
    ):
        raise ValueError("ablation_acceptance_group_leakage")
    profile_file = Path(profile_file)
    profile = load_profiles(profile_file)[profile_id]
    profile.verify_artifacts()
    if importlib.metadata.version("faster-whisper") != profile.runtime_version:
        raise ValueError("ablation_faster_whisper_version_mismatch")
    return suite_path, suite, manifest_path, manifest, profile_file, profile


def run_matched_ablation(
    suite_path,
    profile_file,
    profile_id,
    output_path,
    *,
    compute_budget_seconds=7200,
    resume=False,
):
    if type(compute_budget_seconds) is not int or compute_budget_seconds <= 0:
        raise ValueError("positive_ablation_compute_budget_required")
    (
        suite_path,
        suite,
        manifest_path,
        manifest,
        profile_file,
        profile,
    ) = _profile_and_manifest(suite_path, profile_file, profile_id)
    output_path = Path(output_path)
    if output_path.exists():
        raise ValueError("preserve_existing_ablation_receipt")
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial")
    from services.asr import ablation as ablation_module
    from services.asr import energy_vad_chunking

    service_root = Path(__file__).resolve().parents[1]
    source_files = [
        Path(__file__),
        Path(ablation_module.__file__),
        Path(energy_vad_chunking.__file__),
        service_root / "asr" / "context_biasing.py",
        service_root / "evaluation.py",
    ]
    source_sha256 = {
        str(path.resolve()).replace("\\", "/"): file_sha256(path)
        for path in source_files
    }
    runner_sha = source_sha256[str(Path(__file__).resolve()).replace("\\", "/")]
    lexicon_path = Path("evaluation/lexicons/clinical-english-v1-e01.json")
    lexicon_sha = file_sha256(lexicon_path)
    lexicon = json.loads(lexicon_path.read_text(encoding="utf-8"))
    bias = build_context_bias([entry["term"] for entry in lexicon["entries"]])
    configurations = {
        arm_id: {
            "base_model_sha256": profile.sha256,
            "changed_components": list(ARM_COMPONENTS[arm_id]),
            "compute_budget_seconds": compute_budget_seconds,
            "training_group_scope": "same_pretrained_weights_no_project_finetuning",
            "component_parameters": {
                **(
                    {
                        "vad_profile": ENERGY_VAD_CONFIG,
                        "vad_profile_sha256": hashlib.sha256(
                            json.dumps(
                                ENERGY_VAD_CONFIG,
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode("utf-8")
                        ).hexdigest(),
                    }
                    if "vad" in ARM_COMPONENTS[arm_id]
                    else {}
                ),
                **(
                    {"beam_size": 1}
                    if "decoder" in ARM_COMPONENTS[arm_id]
                    else {"beam_size": profile.beam_size}
                ),
                **(
                    {
                        "lexicon_sha256": lexicon_sha,
                        "hotwords": bias["hotwords"],
                    }
                    if "terminology" in ARM_COMPONENTS[arm_id]
                    else {}
                ),
                **(
                    {
                        "repair_policy": "fixed_lexical_risk_pattern_v1",
                        "padding_frames": REPAIR_PADDING_FRAMES,
                        "maximum_repairs_per_case": MAX_REPAIRS_PER_CASE,
                    }
                    if "repair" in ARM_COMPONENTS[arm_id]
                    else {}
                ),
            },
        }
        for arm_id in ARM_IDS
    }
    bindings = {
        "suite_sha256": file_sha256(suite_path),
        "manifest_sha256": suite["manifest_sha256"],
        "profile_sha256": profile.sha256,
        "profile_file_sha256": file_sha256(profile_file),
        "lexicon_sha256": lexicon_sha,
        "runner_sha256": runner_sha,
        "source_sha256": source_sha256,
    }
    protocol = {
        "compute_budget_seconds": compute_budget_seconds,
        "configurations": configurations,
        "repair_adoption": "candidate_evaluation_only_not_application_adoption",
    }
    if checkpoint_path.exists():
        if not resume:
            raise ValueError("partial_ablation_exists_resume_or_preserve_it")
        partial = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if partial.get("bindings") != bindings or partial.get("protocol") != protocol:
            raise ValueError("ablation_resume_configuration_changed")
    else:
        if resume:
            raise ValueError("ablation_resume_receipt_missing")
        partial = {
            "schema_version": "matched_asr_ablation_checkpoint_v1",
            "bindings": bindings,
            "protocol": protocol,
            "arm_outputs": {
                arm_id: {
                    "configuration": configurations[arm_id],
                    "training_group_ids": [],
                    "cases": [],
                }
                for arm_id in ARM_IDS
            },
        }
        atomic_json(checkpoint_path, partial)

    from faster_whisper import WhisperModel

    load_started = time.perf_counter()
    model = WhisperModel(
        profile.model_dir,
        device=profile.device,
        compute_type=profile.compute_type,
        cpu_threads=profile.cpu_threads,
        num_workers=1,
        local_files_only=True,
    )
    model_load_seconds = time.perf_counter() - load_started
    source_root = Path(suite["audio_root"])
    for arm_id in ARM_IDS:
        arm = partial["arm_outputs"][arm_id]
        done = {row["group_id"] for row in arm["cases"]}
        arm_started = time.perf_counter()
        components = ARM_COMPONENTS[arm_id]
        beam_size = 1 if "decoder" in components else profile.beam_size
        hotwords = bias["hotwords"] if "terminology" in components else None
        for case in manifest["cases"]:
            if case["group_id"] in done:
                continue
            path = source_root / case["audio"]
            started = time.perf_counter()
            try:
                row = _run_case(
                    model,
                    case,
                    path,
                    arm_id,
                    beam_size,
                    hotwords,
                    ENERGY_VAD_CONFIG,
                )
            except Exception as exc:
                row = {
                    "group_id": case["group_id"],
                    "audio_sha256": case["audio_sha256"],
                    "reference_sha256": hashlib.sha256(
                        _reference(case).encode("utf-8")
                    ).hexdigest(),
                    "condition": case["condition"],
                    "foreground_id": case["foreground_id"],
                    "donor_id": case.get("donor_id"),
                    "hypothesis": "",
                    "failed": True,
                    "failure_code": type(exc).__name__,
                    "wall_seconds": time.perf_counter() - started,
                    "repair_candidates": [],
                }
            score_reference = score(_reference(case), row["hypothesis"])
            row.update(
                reference_words=score_reference["reference_words"],
                normalized_edits=score_reference["normalized_edits"],
            )
            arm["cases"].append(row)
            elapsed = sum(item["wall_seconds"] for item in arm["cases"])
            if elapsed > compute_budget_seconds:
                atomic_json(checkpoint_path, partial)
                raise TimeoutError("matched_ablation_arm_compute_budget_exceeded")
            atomic_json(checkpoint_path, partial)
        arm["wall_seconds"] = sum(row["wall_seconds"] for row in arm["cases"])
        if arm["wall_seconds"] > compute_budget_seconds:
            atomic_json(checkpoint_path, partial)
            raise TimeoutError("matched_ablation_arm_compute_budget_exceeded")
        arm["arm_elapsed_seconds"] = time.perf_counter() - arm_started
        atomic_json(checkpoint_path, partial)

    from services.detailed_benchmark import process_peak_resident_bytes

    try:
        peak_bytes, peak_method = process_peak_resident_bytes()
        resource = {
            "status": "measured",
            "peak_resident_bytes": peak_bytes,
            "method": peak_method,
        }
    except (OSError, ImportError, AttributeError):
        resource = {
            "status": "unavailable",
            "peak_resident_bytes": None,
            "method": None,
        }
    summary = summarize_matched_ablation(
        [
            {
                "group_id": case["group_id"],
                "audio_sha256": case["audio_sha256"],
                "reference": _reference(case),
                "condition": case["condition"],
                "foreground_id": case["foreground_id"],
                "donor_id": case.get("donor_id"),
            }
            for case in manifest["cases"]
        ],
        [
            {
                "arm_id": arm_id,
                "configuration": partial["arm_outputs"][arm_id]["configuration"],
                "training_group_ids": [],
                "wall_seconds": partial["arm_outputs"][arm_id]["wall_seconds"],
                "cases": partial["arm_outputs"][arm_id]["cases"],
            }
            for arm_id in ARM_IDS
        ],
    )
    report = {
        "schema_version": "matched_asr_ablation_receipt_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "reference_status": manifest.get("clinician_adjudication", "unknown"),
        "bindings": bindings,
        "protocol": protocol,
        "model_load_seconds": model_load_seconds,
        "resource_measurement": resource,
        "comparison": summary,
        "arm_outputs": partial["arm_outputs"],
    }
    published = publish_json_once(output_path, report)
    checkpoint_path.unlink(missing_ok=True)
    return published


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="evaluation/detailed-suite-v7.json")
    parser.add_argument("--profiles", default="data/asr-smoke-profiles.json")
    parser.add_argument("--profile-id", default="tiny-en-smoke-v1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--compute-budget-seconds", type=int, default=7200)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = run_matched_ablation(
        args.suite,
        args.profiles,
        args.profile_id,
        args.output,
        compute_budget_seconds=args.compute_budget_seconds,
        resume=args.resume,
    )
    print(json.dumps(result["comparison"], sort_keys=True))


if __name__ == "__main__":
    main()
