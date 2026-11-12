"""Measure local enhancement CPU time and sampled process RSS on frozen audio."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import threading
import time

import psutil

from services.audio_enhancement import (
    highpass_transform,
    normalize_rms_transform,
    spectral_gate_transform,
)
from services.audio_provenance import file_sha256


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _measure(transform, source, target, sample_interval_seconds):
    process = psutil.Process(os.getpid())
    baseline_rss = process.memory_info().rss
    peak_rss = baseline_rss
    stop = threading.Event()

    def sample_rss():
        nonlocal peak_rss
        while not stop.is_set():
            try:
                peak_rss = max(peak_rss, process.memory_info().rss)
            except psutil.Error:
                return
            stop.wait(sample_interval_seconds)

    monitor = threading.Thread(target=sample_rss, daemon=True)
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    monitor.start()
    try:
        transform(source, target)
    finally:
        stop.set()
        monitor.join()
    return {
        "cpu_seconds": time.process_time() - cpu_start,
        "wall_seconds": time.perf_counter() - wall_start,
        "baseline_process_rss_bytes": baseline_rss,
        "peak_sampled_process_rss_bytes": peak_rss,
        "sampled_peak_rss_delta_bytes": max(0, peak_rss - baseline_rss),
        "rss_sampling_interval_ms": sample_interval_seconds * 1000,
    }


def run(
    manifest_path="evaluation/datasets/primock57-smoke-v1/manifest.json",
    audio_root="data/datasets/primock57-smoke",
    output_path="evaluation/reports/audio-filter-resource-v1.json",
    sample_interval_seconds=0.005,
):
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("data_class") != "approved_public" or not manifest.get(
        "rights_reviewed"
    ):
        raise ValueError("rights_reviewed_public_manifest_required")
    if not 0.001 <= sample_interval_seconds <= 0.1:
        raise ValueError("invalid_rss_sampling_interval")
    transforms = (
        ("rms_level_normalization_v1", normalize_rms_transform(-23.0, 0.98)),
        ("highpass_80hz_v1", highpass_transform(80, 4)),
        (
            "spectral_gate_percentile25_v1",
            spectral_gate_transform(25, 1.5, 0.15),
        ),
    )
    rows = []
    for sample in manifest["samples"]:
        source = Path(audio_root) / sample["audio"]
        if file_sha256(source) != sample["audio_sha256"]:
            raise ValueError("source_audio_manifest_digest_mismatch")
        import wave

        with wave.open(str(source), "rb") as audio:
            duration_seconds = audio.getnframes() / audio.getframerate()
        for transform_id, transform in transforms:
            target = source.with_name(f".{source.stem}-{transform_id}.wav")
            if target.exists():
                raise ValueError("benchmark_output_already_exists")
            try:
                metrics = _measure(transform, source, target, sample_interval_seconds)
                if file_sha256(source) != sample["audio_sha256"]:
                    raise ValueError("benchmark_source_audio_was_modified")
                rows.append(
                    {
                        "sample_id": sample["sample_id"],
                        "source_sha256": sample["audio_sha256"],
                        "transform_id": transform_id,
                        "duration_seconds": duration_seconds,
                        "real_time_factor_wall": metrics["wall_seconds"]
                        / duration_seconds,
                        "real_time_factor_cpu": metrics["cpu_seconds"]
                        / duration_seconds,
                        **metrics,
                    }
                )
            finally:
                target.unlink(missing_ok=True)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "audio_filter_resource_benchmark_v1",
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": file_sha256(manifest_file),
        "source_code_sha256": {
            path: file_sha256(path)
            for path in (
                "services/audio_filter_benchmark.py",
                "services/audio_enhancement.py",
            )
        },
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor() or None,
            "logical_cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "psutil": importlib.metadata.version("psutil"),
        },
        "summary": {
            "sample_count": len(manifest["samples"]),
            "transform_count": len(transforms),
            "measurement_count": len(rows),
            "maximum_tested_duration_seconds": max(
                row["duration_seconds"] for row in rows
            ),
            "maximum_cpu_seconds": max(row["cpu_seconds"] for row in rows),
            "maximum_wall_rtf": max(row["real_time_factor_wall"] for row in rows),
            "maximum_cpu_rtf": max(row["real_time_factor_cpu"] for row in rows),
            "maximum_sampled_process_rss_bytes": max(
                row["peak_sampled_process_rss_bytes"] for row in rows
            ),
        },
        "measurement_limits": [
            "RSS is process-wide and sampled, so short-lived allocation peaks may be missed.",
            "The benchmark excludes ASR model memory and measures only enhancement transforms.",
            "Maximum duration is the longest tested smoke clip, not a supported media limit.",
            "Results describe this machine and current process environment only.",
        ],
        "measurements": rows,
    }
    with output.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(payload, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", default="evaluation/datasets/primock57-smoke-v1/manifest.json"
    )
    parser.add_argument("--audio-root", default="data/datasets/primock57-smoke")
    parser.add_argument(
        "--out", default="evaluation/reports/audio-filter-resource-v1.json"
    )
    args = parser.parse_args()
    report = run(args.manifest, args.audio_root, args.out)
    print(json.dumps(report["summary"], indent=2))
