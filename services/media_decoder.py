"""Resource-bounded, separate-process audio decoding and channel-preserving 16 kHz normalization."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path


FORMATS = {
    "audio/wav": {"wav"},
    "audio/mpeg": {"mp3"},
    "audio/mp4": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
    "audio/webm": {"matroska", "webm"},
    "audio/ogg": {"ogg"},
}


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _failure_result(
    error_code,
    stage,
    source,
    destination,
    media_type,
    started,
    *,
    source_sha256=None,
    process_returncode=None,
    child_error_code=None,
    stdout=b"",
    timed_out=False,
    timeout_seconds=None,
):
    """Return a bounded, content-free failure receipt for a decode attempt."""
    source_bytes = None
    observed_source_sha256 = None
    output_bytes, output_sha256 = None, None
    try:
        source_bytes = source.stat().st_size
        if source_bytes <= 512_000_000:
            digest = hashlib.sha256()
            with source.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            observed_source_sha256 = digest.hexdigest()
    except OSError:
        pass
    try:
        output_bytes = destination.stat().st_size
        if output_bytes <= 512_000_000:
            digest = hashlib.sha256()
            with destination.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            output_sha256 = digest.hexdigest()
    except OSError:
        pass
    return {
        "error_code": error_code,
        "failure_report": {
            "schema_version": "audio_decoder_failure_v1",
            "status": "failed",
            "stage": stage,
            "error_code": error_code,
            "media_type": media_type,
            "source_name": source.name,
            "source_bytes": source_bytes,
            "source_sha256": source_sha256,
            "observed_source_sha256": observed_source_sha256,
            "destination_name": destination.name,
            "partial_output_bytes": output_bytes,
            "partial_output_sha256": output_sha256,
            "process_returncode": process_returncode,
            "child_error_code": child_error_code,
            "stdout_bytes": len(stdout),
            "stdout_sha256": _sha256_bytes(stdout) if stdout else None,
            "timed_out": timed_out,
            "timeout_seconds": timeout_seconds,
            "elapsed_ms": max(0, round((time.monotonic() - started) * 1000)),
            "raw_diagnostics_retained": False,
            "diagnostics_policy": "Preserve hashes and bounded failure metadata; do not retain raw decoder output that may contain source data.",
        },
    }


def decode_child(source, destination, media_type):
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
        resource.setrlimit(resource.RLIMIT_FSIZE, (512_000_000, 512_000_000))
    try:
        import av
    except ImportError:
        return {"error_code": "media_dependency_missing"}
    total = 0
    try:
        with av.open(str(source), options={"protocol_whitelist": "file"}) as container:
            if not set(container.format.name.split(",")) & FORMATS[media_type]:
                return {"error_code": "media_type_mismatch"}
            if len(container.streams.audio) != 1 or len(container.streams.video):
                return {"error_code": "unsupported_media_streams"}
            stream = container.streams.audio[0]
            channels = len(stream.codec_context.layout.channels)
            if not 1 <= channels <= 8:
                return {"error_code": "unsupported_audio_profile"}
            source_rate = stream.codec_context.sample_rate or stream.rate
            source_rate = int(source_rate) if source_rate else None
            if source_rate is None or not 8000 <= source_rate <= 48000:
                return {"error_code": "unsupported_audio_profile"}
            time_base = stream.time_base
            source_origin_ms = None
            if stream.start_time is not None and time_base is not None:
                source_origin_ms = float(stream.start_time * time_base * 1000)
            source_format = container.format.name
            resampler = av.AudioResampler(
                format="s16", layout=stream.codec_context.layout, rate=16000
            )
            with wave.open(str(destination), "wb") as target:
                target.setparams((channels, 2, 16000, 0, "NONE", "not compressed"))
                for frame in container.decode(stream):
                    if (
                        len(frame.layout.channels) != channels
                        or frame.sample_rate != source_rate
                    ):
                        return {"error_code": "unsupported_audio_profile"}
                    for output in resampler.resample(frame):
                        if (
                            output.sample_rate != 16000
                            or len(output.layout.channels) != channels
                            or output.format.name not in ("s16", "s16p")
                        ):
                            return {"error_code": "unsupported_audio_profile"}
                        total += output.samples
                        if total * channels * 2 + 44 > 512_000_000:
                            return {"error_code": "decoded_size_limit_exceeded"}
                        if total > 16000 * 3600:
                            return {"error_code": "duration_limit_exceeded"}
                        target.writeframes(output.to_ndarray().astype("<i2").tobytes())
                for output in resampler.resample(None):
                    if (
                        output.sample_rate != 16000
                        or len(output.layout.channels) != channels
                        or output.format.name not in ("s16", "s16p")
                    ):
                        return {"error_code": "unsupported_audio_profile"}
                    total += output.samples
                    if total * channels * 2 + 44 > 512_000_000:
                        return {"error_code": "decoded_size_limit_exceeded"}
                    if total > 16000 * 3600:
                        return {"error_code": "duration_limit_exceeded"}
                    target.writeframes(output.to_ndarray().astype("<i2").tobytes())
        return (
            {
                "frames": total,
                "error_code": None,
                "source_sample_rate": source_rate,
                "source_channels": channels,
                "source_origin_ms": source_origin_ms,
                "source_container": source_format,
                "output_sample_rate": 16000,
                "output_channels": channels,
                "output_encoding": "pcm_s16le",
            }
            if total
            else {"error_code": "empty_audio"}
        )
    except Exception:
        return {"error_code": "invalid_media"}


def normalize(source, destination, media_type):
    from services.audio_provenance import (
        derive_provenance,
        file_sha256,
        normalization_timeline,
        source_provenance,
    )

    started = time.monotonic()
    source_path, destination_path = Path(source), Path(destination)
    try:
        source = source.resolve()
        destination = destination_path.resolve()
        parent = source_provenance(source, media_type)
    except (OSError, ValueError):
        return _failure_result(
            "decoder_process_failed",
            "source_validation",
            source_path,
            destination_path,
            media_type,
            started,
        )
    # Keep provider credentials and application policy state out of the child environment.
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LD_LIBRARY_PATH"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", AV_LOG_FORCE_NOCOLOR="1")
    child = Path(__file__).resolve()
    command = [
        sys.executable,
        "-I",
        str(child),
        "--child",
        "--source",
        str(source),
        "--destination",
        str(destination),
        "--media-type",
        media_type,
    ]
    try:
        result = subprocess.run(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode or len(result.stdout) > 4096:
            return _failure_result(
                "decoder_process_failed",
                "decoder_process",
                source,
                destination,
                media_type,
                started,
                source_sha256=parent["asset_sha256"],
                process_returncode=result.returncode,
                stdout=result.stdout,
            )
        decoded = json.loads(result.stdout)
        if decoded.get("error_code"):
            return _failure_result(
                decoded["error_code"],
                "decoder_child",
                source,
                destination,
                media_type,
                started,
                source_sha256=parent["asset_sha256"],
                process_returncode=result.returncode,
                child_error_code=decoded["error_code"],
                stdout=result.stdout,
            )
        if file_sha256(source) != parent["asset_sha256"]:
            return _failure_result(
                "source_audio_changed_during_normalization",
                "source_integrity_check",
                source,
                destination,
                media_type,
                started,
                source_sha256=parent["asset_sha256"],
                process_returncode=result.returncode,
                stdout=result.stdout,
            )
        decoded["audio_provenance"] = derive_provenance(
            parent,
            destination,
            "pyav_resample_to_pcm_s16le_v1",
            {
                "media_type": media_type,
                "decoder": "PyAV",
                "source_container": decoded.get("source_container"),
                "source_sample_rate": decoded.get("source_sample_rate"),
                "source_channels": decoded.get("source_channels"),
                "output_sample_rate": decoded["output_sample_rate"],
                "output_channels": decoded["output_channels"],
                "output_encoding": decoded["output_encoding"],
            },
            normalization_timeline(
                decoded.get("source_sample_rate"),
                decoded["output_sample_rate"],
                decoded.get("source_origin_ms"),
            ),
        )
        return decoded
    except subprocess.TimeoutExpired as exc:
        return _failure_result(
            "decoder_timeout",
            "decoder_process",
            source,
            destination,
            media_type,
            started,
            source_sha256=parent["asset_sha256"],
            timed_out=True,
            timeout_seconds=120,
            stdout=exc.stdout or b"",
        )
    except (OSError, ValueError):
        return _failure_result(
            "decoder_process_failed",
            "decoder_process",
            source,
            destination,
            media_type,
            started,
            source_sha256=parent["asset_sha256"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--media-type", choices=FORMATS, required=True)
    args = parser.parse_args()
    print(json.dumps(decode_child(args.source, args.destination, args.media_type)))
