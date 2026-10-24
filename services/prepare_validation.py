"""Prepare the predeclared five-consultation validation corpus without model-dependent selection."""

import argparse
import json
import re
import wave
from pathlib import Path

from services.api.ingest import file_sha256
from services.media_decoder import normalize
from services.prepare_primock import ATTRIBUTION, RAW, MEDIA, REVISION, download, intervals


def prepare(destination, protocol_path="evaluation/validation-protocol-v1.json"):
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    if protocol["source_revision"] != REVISION:
        raise ValueError("Protocol/source revision mismatch")
    root = Path(destination)
    if (root / "manifest.json").exists():
        raise ValueError("Validation corpus already exists; do not overwrite a frozen manifest")
    root.mkdir(parents=True, exist_ok=True)
    sources, samples = [], []
    license_text = download(f"{RAW}/LICENSE.md", root / "LICENSE.md", 100_000).decode("utf-8")
    if "Creative Commons Attribution 4.0 International" not in license_text:
        raise ValueError("Unexpected upstream dataset license")
    for consultation in protocol["consultations"]:
        if not re.fullmatch(r"day\d+_consultation\d+", consultation):
            raise ValueError("Invalid source consultation")
        for role in protocol["roles"]:
            if role not in ("doctor", "patient"):
                raise ValueError("Invalid role")
            stem = f"{consultation}_{role}"
            pointer = download(f"{RAW}/audio/{stem}.wav", root / f"{stem}.lfs", 1000).decode()
            checksum = re.search(r"oid sha256:([a-f0-9]{64})", pointer).group(1)
            size = int(re.search(r"size (\d+)", pointer).group(1))
            original = root / f"{stem}.original.wav"
            if not original.exists() or original.stat().st_size != size or file_sha256(original) != checksum:
                download(f"{MEDIA}/audio/{stem}.wav", original)
            if original.stat().st_size != size or file_sha256(original) != checksum:
                raise ValueError("Upstream LFS integrity failure")
            grid = root / f"{stem}.TextGrid"
            text = download(f"{RAW}/transcripts/{stem}.TextGrid", grid, 200_000).decode("utf-8-sig")
            normalized = root / f"{stem}.normalized.wav"
            result = normalize(original, normalized, "audio/wav")
            if result.get("error_code"):
                raise ValueError(f"Normalization failed: {result['error_code']}")
            chosen = [(a, b, words) for a, b, words in intervals(text)
                      if 4 <= b-a <= 20 and len(words.split()) >= 5 and "<" not in words][:protocol["utterances_per_role"]]
            if not chosen or (protocol.get("require_full_role_count", True) and len(chosen) != protocol["utterances_per_role"]):
                raise ValueError("Predeclared selection cannot be fulfilled; do not silently substitute samples")
            with wave.open(str(normalized), "rb") as audio:
                rate, frames = audio.getframerate(), audio.getnframes()
                for index, (start, end, words) in enumerate(chosen, 1):
                    first = max(0, int((start-protocol["padding_seconds"])*rate))
                    last = min(frames, int((end+protocol["padding_seconds"])*rate))
                    audio.setpos(first)
                    pcm = audio.readframes(last-first)
                    target = root / f"{stem}.utterance{index:02}.wav"
                    with wave.open(str(target), "wb") as output:
                        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                        output.writeframes(pcm)
                    samples.append({"sample_id": target.stem, "group_id": consultation, "speaker_role": role,
                        "language": "en", "audio": target.name, "audio_sha256": file_sha256(target), "reference": words,
                        "source_start_seconds": first/rate, "source_end_seconds": last/rate})
            sources.append({"source": f"{MEDIA}/audio/{stem}.wav", "audio_sha256": checksum,
                "annotation_sha256": file_sha256(grid)})
            print(f"Prepared {stem}", flush=True)
    manifest = {"dataset_id": protocol["dataset_id"], "split_role": protocol["split_role"],
        "data_class": "approved_public", "rights_reviewed": True, "license_id": "CC-BY-4.0",
        "attribution": ATTRIBUTION, "source_revision": REVISION, "protocol_sha256": file_sha256(Path(protocol_path)),
        "selection": protocol["selection"], "changes": "Mono 16kHz PCM16; utterance crops with 250ms padding; references unchanged.",
        "limitations": protocol["limitations"], "sources": sources, "samples": samples}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (root / "ATTRIBUTION.txt").write_text(ATTRIBUTION + "\n" + manifest["changes"], encoding="utf-8")
    print(f"Frozen manifest: {file_sha256(path)}", flush=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default="data/datasets/primock57-validation-v1")
    parser.add_argument("--protocol", default="evaluation/validation-protocol-v1.json")
    args = parser.parse_args()
    print(prepare(args.destination, args.protocol))


if __name__ == "__main__":
    main()
