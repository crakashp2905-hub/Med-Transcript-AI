"""Download a pinned public mock-consultation sample for local ASR evaluation.

Network access occurs only in this explicit preparation command, never inference.
PriMock57: Papadopoulos Korfiatis, Moramarco, Sarac and Savkov (2022), CC BY 4.0.
"""

import argparse
import hashlib
import json
import re
import urllib.request
import wave
from pathlib import Path

from services.api.ingest import file_sha256
from services.media_decoder import normalize


REVISION = "cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5"
REPOSITORY = "https://github.com/babylonhealth/primock57"
RAW = f"https://raw.githubusercontent.com/babylonhealth/primock57/{REVISION}"
MEDIA = f"https://media.githubusercontent.com/media/babylonhealth/primock57/{REVISION}"
ATTRIBUTION = ("PriMock57: A Dataset Of Primary Care Mock Consultations, "
    "Alex Papadopoulos Korfiatis, Francesco Moramarco, Radmila Sarac and Aleksandar Savkov (2022), "
    "Babylon Health. CC BY 4.0. Source: " + REPOSITORY)


def download(url, destination, limit=50_000_000):
    with urllib.request.urlopen(url, timeout=120) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Dataset download exceeds the preparation limit")
    destination.write_bytes(content)
    return content


def intervals(text):
    pattern = r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "((?:[^\"]|\"\")*)"'
    return [(float(start), float(end), words.replace('""', '"').strip())
            for start, end, words in re.findall(pattern, text)]


def prepare(destination):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    license_text = download(f"{RAW}/LICENSE.md", root / "LICENSE.md", 100_000).decode("utf-8")
    if "Creative Commons Attribution 4.0 International" not in license_text:
        raise ValueError("Unexpected upstream dataset license")
    samples, provenance = [], []
    for role in ("doctor", "patient"):
        stem = f"day1_consultation01_{role}"
        pointer = download(f"{RAW}/audio/{stem}.wav", root / f"{stem}.lfs", 1000).decode()
        digest = re.search(r"oid sha256:([a-f0-9]{64})", pointer).group(1)
        size = int(re.search(r"size (\d+)", pointer).group(1))
        original = root / f"{stem}.original.wav"
        if not original.exists() or file_sha256(original) != digest:
            download(f"{MEDIA}/audio/{stem}.wav", original)
        if original.stat().st_size != size or file_sha256(original) != digest:
            raise ValueError("Original dataset audio does not match its pinned LFS object")
        grid = root / f"{stem}.TextGrid"
        annotation = download(f"{RAW}/transcripts/{stem}.TextGrid", grid, 200_000).decode("utf-8-sig")
        normalized = root / f"{stem}.normalized.wav"
        result = normalize(original, normalized, "audio/wav")
        if result.get("error_code"):
            raise ValueError(f"Normalization failed: {result['error_code']}")
        with wave.open(str(normalized), "rb") as audio:
            rate, frames = audio.getframerate(), audio.getnframes()
            # Deterministic first three eligible utterances, selected before inference.
            # Tagged uncertain/unintelligible references are excluded from this smoke subset.
            selected = [(start, end, words) for start, end, words in intervals(annotation)
                        if 4 <= end-start <= 20 and len(words.split()) >= 5 and "<" not in words][:3]
            if len(selected) != 3:
                raise ValueError("Pinned annotation no longer yields three eligible utterances")
            for index, (start, end, words) in enumerate(selected, 1):
                first, last = max(0, int((start-0.25)*rate)), min(frames, int((end+0.25)*rate))
                audio.setpos(first)
                pcm = audio.readframes(last-first)
                clip = root / f"{stem}.utterance{index:02}.wav"
                with wave.open(str(clip), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(rate)
                    output.writeframes(pcm)
                samples.append({"sample_id": clip.stem, "group_id": "day1_consultation01",
                    "language": "en", "audio": clip.name, "audio_sha256": file_sha256(clip),
                    "reference": words, "speaker_role": role, "source_start_seconds": first/rate,
                    "source_end_seconds": last/rate})
        provenance.append({"source": f"{MEDIA}/audio/{stem}.wav", "audio_sha256": digest,
            "annotation_sha256": hashlib.sha256(grid.read_bytes()).hexdigest()})
    manifest = {"dataset_id": "primock57-consultation01-six-utterance-smoke-v1",
        "split_role": "development_smoke_not_acceptance", "data_class": "approved_public",
        "rights_reviewed": True, "license_id": "CC-BY-4.0", "attribution": ATTRIBUTION,
        "source_revision": REVISION, "sources": provenance,
        "changes": "Normalized to mono 16kHz PCM; first three 4–20 second untagged utterances per role, 250ms padding.",
        "limitations": "One consultation, separate speaker tracks, selected clean utterances; not clinical validation or conversation diarization.",
        "samples": samples}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (root / "ATTRIBUTION.txt").write_text(ATTRIBUTION + "\n" + manifest["changes"], encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default="data/datasets/primock57-smoke")
    args = parser.parse_args()
    print(prepare(args.destination))


if __name__ == "__main__":
    main()
