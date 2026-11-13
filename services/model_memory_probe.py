"""Measure local ASR model load/inference RSS without network or text capture."""

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import subprocess
import time
import wave
from pathlib import Path

import psutil

from services.api.ingest import file_sha256
from services.detailed_benchmark import load, process_peak_resident_bytes
from services.inference_slot import estimate_model_request_bytes, local_inference_slot


ROOT = Path(__file__).resolve().parents[1]


def _inside_root(path):
    path = Path(path).resolve(strict=True)
    if not path.is_relative_to(ROOT):
        raise ValueError("probe_path_outside_repository")
    return path


def _audio_metadata(path):
    path = _inside_root(path)
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (
            1,
            2,
            16000,
        ):
            raise ValueError("probe_requires_mono_16khz_pcm16")
        frames = audio.getnframes()
    if frames < 1:
        raise ValueError("probe_audio_empty")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": file_sha256(path),
        "frames": frames,
        "duration_seconds": frames / 16000,
    }


def _job(suite_path, candidate_id):
    suite_path = _inside_root(suite_path)
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    matches = [job for job in suite["jobs"] if job["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise ValueError("probe_candidate_not_unique_in_suite")
    return suite_path, suite, matches[0]


def _model_artifacts(job):
    if job["runtime"] == "whisper":
        from services.asr.profiles import load_profiles

        profile_path = ROOT / "data" / job["profile_file"]
        profile = load_profiles(profile_path)[job["profile_id"]]
        if profile.sha256 != job["source_profile_sha256"]:
            raise ValueError("probe_profile_digest_mismatch")
        profile.verify_artifacts()
        return [Path(profile.model_dir) / name for name in profile.artifacts]
    root = _inside_root(job["model_dir"])
    for name, digest in job["expected_artifacts"].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or file_sha256(path) != digest:
            raise ValueError("probe_model_artifact_digest_mismatch")
    return [root / name for name in job["expected_artifacts"]]


def _memory_snapshot(process):
    return {
        "process_rss_bytes": process.memory_info().rss,
        "system_available_bytes": psutil.virtual_memory().available,
    }


def _cuda_available():
    if importlib.util.find_spec("onnxruntime") is None:
        return None
    import onnxruntime

    return "CUDAExecutionProvider" in onnxruntime.get_available_providers()


def run_probe(suite_file, candidate_id, audio_file):
    suite_path, suite, job = _job(suite_file, candidate_id)
    audio = _audio_metadata(audio_file)
    artifacts = _model_artifacts(job)
    request_bytes = estimate_model_request_bytes(artifacts)
    process = psutil.Process()
    receipt = {
        "schema_version": "local_model_memory_probe_v1",
        "candidate_id": candidate_id,
        "status": "deferred",
        "suite_sha256": file_sha256(suite_path),
        "audio": audio,
        "runtime": None,
        "host": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "physical_ram_bytes": psutil.virtual_memory().total,
            "cuda_available": _cuda_available(),
        },
        "admission": {
            "requested_bytes": request_bytes,
            "reserve_bytes": 2 * 1024**3,
            "policy": "local_inference_slot_shared_memory_admission",
        },
        "memory": {"before_model_load": _memory_snapshot(process)},
        "timing": {},
        "hypothesis_characters": None,
        "clinical_quality_evaluated": False,
        "external_calls_attempted": 0,
        "model_text_persisted": False,
    }
    with local_inference_slot(requested_bytes=request_bytes) as admitted:
        if not admitted:
            receipt["admission"]["status"] = "deferred"
            return receipt
        receipt["admission"]["status"] = "admitted"
        model = None
        started = time.perf_counter()
        try:
            model, config, close = load(job)
            receipt["runtime"] = config
            receipt["timing"]["model_load_seconds"] = time.perf_counter() - started
            receipt["memory"]["after_model_load"] = _memory_snapshot(process)
            inference_started = time.perf_counter()
            result = model(str(ROOT / audio["path"]))
            text = result["text"] if isinstance(result, dict) else result
            if not isinstance(text, str):
                raise ValueError("probe_runtime_output_invalid")
            receipt["timing"]["inference_seconds"] = (
                time.perf_counter() - inference_started
            )
            receipt["memory"]["after_inference"] = _memory_snapshot(process)
            receipt["hypothesis_characters"] = len(text)
            receipt["status"] = "measured"
        except Exception as error:
            receipt["status"] = "failed"
            receipt["failure_type"] = type(error).__name__
        finally:
            if model is not None:
                try:
                    close()
                except Exception:
                    if receipt["status"] == "measured":
                        receipt["status"] = "cleanup_failed"
            try:
                peak, method = process_peak_resident_bytes()
                receipt["memory"].update(
                    peak_resident_bytes=peak, peak_measurement_method=method
                )
            except (OSError, ImportError, AttributeError):
                receipt["memory"]["peak_measurement_method"] = "unavailable"
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="evaluation/detailed-suite-v7.json")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--audio", default="data/demo-sample.wav")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = _inside_root(args.out) if Path(args.out).exists() else ROOT / args.out
    if output.exists() or not output.resolve().is_relative_to(
        ROOT / "evaluation" / "reports"
    ):
        raise ValueError("probe_output_must_be_new_report_path")
    report = run_probe(args.suite, args.candidate, args.audio)
    report["source_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    report["source_sha256"] = {
        name: file_sha256(ROOT / name)
        for name in (
            "services/model_memory_probe.py",
            "services/detailed_benchmark.py",
            "services/inference_slot.py",
        )
    }
    report["runtime_package_versions"] = {}
    for package in (
        "onnx-asr",
        "onnxruntime",
        "faster-whisper",
        "omi-med-stt",
        "sherpa-onnx",
    ):
        try:
            report["runtime_package_versions"][package] = importlib.metadata.version(
                package
            )
        except importlib.metadata.PackageNotFoundError:
            report["runtime_package_versions"][package] = None
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2)
        target.write("\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidate": report["candidate_id"],
                "peak_resident_bytes": report["memory"].get("peak_resident_bytes"),
                "report": output.relative_to(ROOT).as_posix(),
            }
        )
    )


if __name__ == "__main__":
    main()
