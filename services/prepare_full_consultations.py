"""Prepare complete, new public mock consultations; never claim independent acceptance."""
import argparse
import json
import re
import wave
from pathlib import Path

from services.api.ingest import file_sha256
from services.media_decoder import normalize
from services.prepare_primock import ATTRIBUTION, RAW, MEDIA, download, intervals, REVISION


def prepare(destination):
    import numpy as np
    root = Path(destination)
    if (root / "manifest.json").exists():
        raise ValueError("Refusing to overwrite a frozen corpus")
    root.mkdir(parents=True, exist_ok=True)
    license_text = download(f"{RAW}/LICENSE.md", root / "LICENSE.md", 100000).decode()
    if "Creative Commons Attribution 4.0 International" not in license_text:
        raise ValueError("Unexpected license")
    cases = []
    for number in (11, 12, 13):
        group = f"day1_consultation{number:02}"
        turns, tracks, sources = [], [], []
        for role in ("doctor", "patient"):
            stem = f"{group}_{role}"
            pointer = download(f"{RAW}/audio/{stem}.wav", root / f"{stem}.lfs", 1000).decode()
            digest = re.search(r"sha256:([a-f0-9]{64})", pointer).group(1)
            size = int(re.search(r"size (\d+)", pointer).group(1))
            source = root / f"{stem}.original.wav"
            if not source.exists() or file_sha256(source) != digest:
                download(f"{MEDIA}/audio/{stem}.wav", source, min(size+1, 250000000))
            if source.stat().st_size != size or file_sha256(source) != digest:
                raise ValueError("Source integrity failure")
            target = root / f"{stem}.wav"
            if normalize(source, target, "audio/wav").get("error_code"):
                raise ValueError("Normalization failed")
            with wave.open(str(target), "rb") as audio:
                tracks.append(np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2"))
            grid = root / f"{stem}.TextGrid"
            text = download(f"{RAW}/transcripts/{stem}.TextGrid", grid, 500000).decode("utf-8-sig")
            turns.extend({"start_ms": round(a*1000), "end_ms": round(b*1000), "role": role,
                "reference": words, "uncertain_reference": "<" in words} for a,b,words in intervals(text) if words)
            sources.append({"role": role, "original_sha256": digest, "annotation_sha256": file_sha256(grid),
                "normalized_audio": target.name, "normalized_sha256": file_sha256(target)})
        count = max(map(len, tracks))
        if not 300 <= count/16000 <= 1800:
            raise ValueError("Full consultation outside predeclared 5–30 minute range")
        mixed = np.zeros(count, dtype=np.int32)
        for track in tracks:
            mixed[:len(track)] += track.astype(np.int32)
        target = root / f"{group}.mixed.wav"
        with wave.open(str(target), "wb") as out:
            out.setparams((1,2,16000,0,"NONE","not compressed"))
            out.writeframes((mixed//2).astype("<i2").tobytes())
        turns.sort(key=lambda r:(r["start_ms"],r["end_ms"],r["role"]))
        cases.append({"group_id": group, "audio": target.name, "audio_sha256": file_sha256(target),
            "duration_ms": count/16, "sources": sources, "reference_turns": turns})
        print(f"Prepared full consultation {group}: {count/16000:.1f} seconds", flush=True)
    body = {"dataset_id": "primock57-full-development-v1", "source_revision": REVISION,
        "data_class": "approved_public", "license": "CC-BY-4.0", "attribution": ATTRIBUTION,
        "split": "untuned_full_encounter_development_not_acceptance", "clinician_adjudication": "pending",
        "limitations": "Source-channel roles are reference labels, not automatic diarization. Track clocks follow upstream annotations; synchronization and overlap require independent review. Uncertain references retained and flagged. No noise/device/speaker independence claim.",
        "cases": cases}
    (root / "manifest.json").write_text(json.dumps(body,indent=2),encoding="utf-8")
    (root / "ATTRIBUTION.txt").write_text(ATTRIBUTION,encoding="utf-8")
    return body


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default="data/datasets/primock57-full-v1")
    args = parser.parse_args()
    prepare(args.destination)
