"""Text-only CPU benchmark adapters. These do not publish clinical transcripts."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

from services.api.ingest import file_sha256, inspect_pcm_wav
from services.asr.profiles import canonical_json
from services.evaluation import PROJECT_MAX_NORMALIZED_WER, score, wer_gate


def run(manifest_path, runtime, model_dir, revision, package_dir, output_path, cache_dir=None,
        maximum=PROJECT_MAX_NORMALIZED_WER, profiles=None, profile_id=None):
    wer_gate({"reference_words": 1, "normalized_edits": 0, "failed_samples": 0}, maximum)
    if maximum > PROJECT_MAX_NORMALIZED_WER:
        raise ValueError("Project policy forbids a normalized WER maximum above 5%")
    if package_dir:
        sys.path.insert(0, str(Path(package_dir).resolve()))
    profile = None
    if runtime == "whisper":
        from services.asr.profiles import load_profiles
        profile = load_profiles(profiles)[profile_id]
        profile.verify_artifacts()
        model_dir, revision = profile.model_dir, profile.revision
    model = Path(model_dir).resolve()
    artifacts = dict(profile.artifacts) if profile else {p.name: file_sha256(p) for p in model.iterdir() if p.is_file()}
    if not artifacts or any(name.endswith('.partial') for name in artifacts):
        raise ValueError("Model artifacts incomplete")
    if runtime == "onnx":
        import onnx_asr
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        recognizer = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", path=str(model),
            quantization="int8", sess_options=options, providers=["CPUExecutionProvider"])
        predict = lambda path: recognizer.recognize(str(path))
        profile_id, package = "parakeet-v2-onnx-cpu-int8-v1", "onnx-asr"
    elif runtime == "omi":
        os.environ["OMI_MED_STT_CACHE"] = str(Path(cache_dir or "data/omi-cache").resolve())
        os.environ["OMI_MED_STT_CPP_REQUIRE_PREBUILT"] = "1"
        from services.omi_adapter import OmiPredictor
        predict = OmiPredictor(model, revision)
        profile_id, package = "omi-v1-gguf-q8-cpu-v1", "omi-med-stt"
    elif runtime == "whisper":
        import wave
        import numpy as np
        from faster_whisper import WhisperModel
        if importlib.metadata.version("faster-whisper") != profile.runtime_version:
            raise ValueError("Profile/runtime mismatch")
        recognizer = WhisperModel(str(model), device=profile.device, compute_type=profile.compute_type,
            cpu_threads=profile.cpu_threads, num_workers=1, local_files_only=True)
        def predict(path):
            with wave.open(str(path), "rb") as audio:
                pcm = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2")
            segments, _ = recognizer.transcribe(pcm.astype(np.float32)/32768.0,
                language="en", task="transcribe", beam_size=profile.beam_size, temperature=0.0,
                vad_filter=False, word_timestamps=False, condition_on_previous_text=False, log_progress=False)
            return " ".join(s.text.strip() for s in segments)
        profile_id, package = profile.profile_id, "faster-whisper"
    else:
        raise ValueError("Unknown runtime")
    config = {"engine": runtime, "profile_id": profile_id, "revision": revision,
        "runtime_version": importlib.metadata.version(package), "artifacts": artifacts,
        "device": "cpu", "threads": 4, "timestamp_support": "not_provided_text_only_evaluation"}
    if profile:
        config.update(source_profile_sha256=profile.sha256, beam_size=profile.beam_size,
            compute_type=profile.compute_type, language="en", temperature=0.0,
            vad_filter=False, condition_on_previous_text=False)
    if runtime == "omi":
        config["adapter_revision"] = "reuse_capi_close_windows_dll_directories_v1"
    path = Path(manifest_path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("data_class") not in ("synthetic", "approved_public") or not manifest.get("rights_reviewed"):
        raise ValueError("Only approved public/synthetic benchmarks are allowed")
    rows = []
    for sample in manifest["samples"]:
        started, hypothesis, error = time.perf_counter(), "", None
        try:
            audio = (path.parent / sample["audio"]).resolve()
            if not audio.is_relative_to(path.parent) or sample["language"] != "en" or file_sha256(audio) != sample["audio_sha256"]:
                raise ValueError("audio_integrity_failure")
            metadata = inspect_pcm_wav(audio)
            if metadata["channels"] != 1 or metadata["sample_rate"] != 16000:
                raise ValueError("unsupported_audio")
            hypothesis = predict(audio)
            if not isinstance(hypothesis, str) or len(hypothesis) > 500_000:
                raise ValueError("invalid_text_output")
            hypothesis.encode("utf-8")
        except Exception:
            hypothesis, error = "", "text_adapter_sample_failed"
        row = {"sample_id": sample["sample_id"], "group_id": sample["group_id"],
            "status": "failed" if error else "completed", "error_code": error,
            "elapsed_seconds": round(time.perf_counter()-started, 4),
            **score(sample["reference"], hypothesis), "reference": sample["reference"], "hypothesis": hypothesis}
        rows.append(row)
        print(json.dumps({"sample_id": row["sample_id"], "status": row["status"]}), flush=True)
    if runtime == "omi":
        predict.close()
    words = sum(r["reference_words"] for r in rows)
    edits = sum(r["normalized_edits"] for r in rows)
    raw_words = sum(r["raw_reference_words"] for r in rows)
    report = {"schema_version": "1.0", "dataset_id": manifest["dataset_id"],
        "manifest_sha256": file_sha256(path), "split_role": manifest["split_role"], "data_class": manifest["data_class"],
        "profile_id": profile_id, "profile_sha256": hashlib.sha256(canonical_json(config).encode()).hexdigest(),
        "model_revision": revision, "runtime_configuration": config,
        "scoring_profile": "lowercase_words_preserve_decimals_units_negation_v1", "sample_count": len(rows),
        "reference_words": words, "normalized_edits": edits, "normalized_wer": edits/words if words else None,
        "raw_wer": sum(r["raw_edits"] for r in rows)/raw_words if raw_words else None,
        "failed_samples": sum(r["status"] == "failed" for r in rows),
        "failure_policy": "empty_hypothesis_full_reference_deletions",
        "critical_error_adjudication": "pending_clinician_review", "clinical_release_gate": "not_evaluated",
        "api_integration_gate": "text_only_adapter_not_admitted_for_clinical_publication", "samples": rows}
    report["wer_gate"] = wer_gate(report, maximum)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("samples", "runtime_configuration")}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--runtime", choices=["onnx", "omi", "whisper"], required=True)
    parser.add_argument("--model-dir")
    parser.add_argument("--revision")
    parser.add_argument("--package-dir")
    parser.add_argument("--profiles")
    parser.add_argument("--profile-id")
    parser.add_argument("--max-normalized-wer", type=float, default=PROJECT_MAX_NORMALIZED_WER)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.runtime == "whisper" and not (args.profiles and args.profile_id):
        parser.error("Whisper requires --profiles and --profile-id")
    if args.runtime != "whisper" and not (args.model_dir and args.revision and args.package_dir):
        parser.error("ONNX/Omi require --model-dir, --revision and --package-dir")
    report = run(args.manifest, args.runtime, args.model_dir, args.revision, args.package_dir, args.out,
        maximum=args.max_normalized_wer, profiles=args.profiles, profile_id=args.profile_id)
    raise SystemExit(0 if report["wer_gate"]["status"] == "pass" else 2)


if __name__ == "__main__":
    main()
