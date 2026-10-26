"""Resource-bounded, separate-process audio decoding and channel-preserving 16 kHz normalization."""

import argparse
import json
import os
import subprocess
import sys
import wave
from pathlib import Path


FORMATS = {"audio/wav": {"wav"}, "audio/mpeg": {"mp3"}, "audio/mp4": {"mov", "mp4", "m4a", "3gp", "3g2", "mj2"},
           "audio/webm": {"matroska", "webm"}, "audio/ogg": {"ogg"}}


def decode_child(source, destination, media_type):
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
        resource.setrlimit(resource.RLIMIT_FSIZE, (250_000_000, 250_000_000))
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
            resampler = av.AudioResampler(format="s16", layout=stream.codec_context.layout, rate=16000)
            with wave.open(str(destination), "wb") as target:
                target.setparams((channels, 2, 16000, 0, "NONE", "not compressed"))
                for frame in container.decode(stream):
                    if len(frame.layout.channels) != channels or not 8000 <= frame.sample_rate <= 48000:
                        return {"error_code": "unsupported_audio_profile"}
                    for output in resampler.resample(frame):
                        total += output.samples
                        if total * channels * 2 + 44 > 250_000_000:
                            return {"error_code": "decoded_size_limit_exceeded"}
                        if total > 16000 * 3600:
                            return {"error_code": "duration_limit_exceeded"}
                        target.writeframes(output.to_ndarray().astype("<i2").tobytes())
                for output in resampler.resample(None):
                    total += output.samples
                    if total * channels * 2 + 44 > 250_000_000:
                        return {"error_code": "decoded_size_limit_exceeded"}
                    if total > 16000 * 3600:
                        return {"error_code": "duration_limit_exceeded"}
                    target.writeframes(output.to_ndarray().astype("<i2").tobytes())
        return {"frames": total, "error_code": None} if total else {"error_code": "empty_audio"}
    except Exception:
        return {"error_code": "invalid_media"}


def normalize(source, destination, media_type):
    # Keep provider credentials and application policy state out of the child environment.
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LD_LIBRARY_PATH"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", AV_LOG_FORCE_NOCOLOR="1")
    child = Path(__file__).resolve()
    command = [sys.executable, "-I", str(child), "--child", "--source", str(Path(source).resolve()),
               "--destination", str(Path(destination).resolve()), "--media-type", media_type]
    try:
        result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if result.returncode or len(result.stdout) > 4096:
            return {"error_code": "decoder_process_failed"}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error_code": "decoder_timeout"}
    except (OSError, ValueError):
        return {"error_code": "decoder_process_failed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--media-type", choices=FORMATS, required=True)
    args = parser.parse_args()
    print(json.dumps(decode_child(args.source, args.destination, args.media_type)))
