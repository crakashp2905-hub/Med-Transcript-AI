"""Create an audible synthetic fixture locally; no downloaded or patient recordings."""

import json
import os
import subprocess
import shutil
import sys
import wave
from pathlib import Path


def create_fixture(root="data"):
    root = Path(root).resolve()
    if (root / "demo-sample.json").is_file() and (root / "demo-sample.wav").is_file():
        return True
    if sys.platform != "win32":
        return False
    parts = root / "synthetic-voice-parts"
    script = Path(__file__).resolve().parents[1] / "scripts" / "create_synthetic_audio.ps1"
    result = subprocess.run([shutil.which("pwsh") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
        "-OutputDirectory", str(parts)], timeout=120, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        return False
    source = json.loads((parts / "segments.json").read_text(encoding="utf-8-sig"))
    segments, frames = [], 0
    with wave.open(str(root / "demo-sample.wav"), "wb") as target:
        target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        for index, item in enumerate(source):
            with wave.open(str(parts / f"{index}.wav"), "rb") as part:
                count = part.getnframes()
                target.writeframes(part.readframes(count))
            segments.append({"start_ms": frames * 1000 // 16000, "end_ms": (frames + count) * 1000 // 16000,
                             "text": item["text"], "role": item["role"]})
            frames += count
    (root / "demo-sample.json").write_text(json.dumps({"fixture_id": "outpatient_english_v1", "synthetic": True,
        "segments": segments}, indent=2), encoding="utf-8")
    return True


if __name__ == "__main__":
    print(json.dumps({"created": create_fixture()}))
