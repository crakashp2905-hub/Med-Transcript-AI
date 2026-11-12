"""Paired development-only evaluation for the pinned local hotwords hook."""

import argparse
import hashlib
import json
import re
import tempfile
import wave
from pathlib import Path

from services.asr.adapter import FasterWhisperAdapter
from services.asr.profiles import ASRProfile
from services.evaluation import score


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def _select_pairs(manifest, term):
    pairs = []
    groups = {}
    for case in manifest.get("cases", []):
        if case.get("condition") != "clean":
            continue
        rows = case.get("reference_turns", [])
        positives = [
            (index, row)
            for index, row in enumerate(rows)
            if row.get("uncertain_reference") is not True
            and isinstance(row.get("reference"), str)
            and re.search(
                rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", row["reference"], re.I
            )
        ]
        if positives:
            groups.setdefault(case.get("foreground_id"), []).append(
                (case, positives[0])
            )
    for group_id in sorted(groups):
        case, (positive_index, positive) = groups[group_id][0]
        negatives = [
            (index, row)
            for index, row in enumerate(case.get("reference_turns", []))
            if row.get("uncertain_reference") is not True
            and isinstance(row.get("reference"), str)
            and row["reference"].strip()
            and not re.search(
                rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",
                row["reference"],
                re.I,
            )
        ]
        if not negatives:
            continue
        negative_index, negative = min(
            negatives, key=lambda item: (abs(item[0] - positive_index), item[0])
        )
        pairs.extend(
            (
                ("positive", case, positive_index, positive),
                ("negative", case, negative_index, negative),
            )
        )
    return pairs


def _crop(source, row, destination):
    with wave.open(str(source), "rb") as audio:
        if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (
            1,
            16000,
            2,
        ):
            raise ValueError("unsupported_development_audio_format")
        start = max(0, int(row["start_ms"]) - 250) * 16
        end = min(audio.getnframes(), (int(row["end_ms"]) + 250) * 16)
        if end <= start:
            raise ValueError("invalid_reference_crop")
        audio.setpos(start)
        frames = audio.readframes(end - start)
        if not frames:
            raise ValueError("empty_reference_crop")
        with wave.open(str(destination), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(frames)
    return {
        "start_ms": start / 16,
        "end_ms": end / 16,
        "pcm_sha256": _sha256_bytes(frames),
        "frames": len(frames) // 2,
    }


def evaluate_bias(manifest_path, audio_root, profile_path, lexicon_path, output_path):
    from services.asr.context_biasing import build_context_bias

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if (
        manifest.get("data_class") != "approved_public"
        or manifest.get("rights_reviewed") is not True
        or "development" not in str(manifest.get("split", "")).lower()
    ):
        raise ValueError("rights_reviewed_development_manifest_required")
    lock_path = manifest_file.parent / "lock.json"
    manifest_digest = _sha256_file(manifest_file)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("manifest_sha256") != manifest_digest:
        raise ValueError("frozen_manifest_lock_mismatch")
    reservation = json.loads(
        Path("evaluation/acceptance-reservation-v1.json").read_text(encoding="utf-8")
    )
    reserved = set(reservation.get("reserved_groups", []))
    if any(
        case.get("foreground_id") in reserved or case.get("donor_id") in reserved
        for case in manifest.get("cases", [])
    ):
        raise ValueError("reserved_acceptance_group_in_eval_source")

    profiles = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    profile_row = next(
        row for row in profiles if row["profile_id"] == "tiny-en-smoke-v1"
    )
    profile = ASRProfile.model_validate(profile_row)
    profile.verify_artifacts()
    lexicon = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
    terms = [entry["term"] for entry in lexicon["entries"]]
    if len(terms) != 1:
        raise ValueError("single_seed_term_required_for_pilot")
    term = terms[0]
    bias = build_context_bias([term])
    pairs = _select_pairs(manifest, term)
    if not pairs:
        raise ValueError("matched_positive_negative_pairs_required")
    adapter = FasterWhisperAdapter(profile)
    rows = []
    with tempfile.TemporaryDirectory(prefix="asr-lexicon-bias-") as temporary:
        for index, (label, case, reference_index, reference_row) in enumerate(pairs):
            source = Path(audio_root) / case["audio"]
            if _sha256_file(source) != case["audio_sha256"]:
                raise ValueError("development_audio_hash_mismatch")
            crop_path = Path(temporary) / f"crop-{index}.wav"
            crop = _crop(source, reference_row, crop_path)
            arm_results = {}
            for arm in ("baseline", "biased"):
                metadata = {
                    "frames": crop["frames"],
                    "channels": 1,
                    "sample_rate": 16000,
                }
                if arm == "biased":
                    metadata["clinical_bias_terms"] = [term]
                try:
                    output = adapter.transcribe(crop_path, metadata, lambda: None)
                    hypothesis = " ".join(
                        segment["text"] for segment in output["segments"]
                    ).strip()
                    arm_results[arm] = {
                        "hypothesis": hypothesis,
                        "failure": False,
                        "context_biasing": output.get("context_biasing"),
                    }
                except Exception as error:
                    arm_results[arm] = {
                        "hypothesis": "",
                        "failure": True,
                        "error_type": type(error).__name__,
                    }
            rows.append(
                {
                    "sample_id": f"{case['group_id']}:{reference_index}:{label}",
                    "group_id": case["foreground_id"],
                    "case_id": case["group_id"],
                    "reference_row_index": reference_index,
                    "reference": reference_row["reference"],
                    "reference_contains_term": label == "positive",
                    "audio_sha256": case["audio_sha256"],
                    "crop": crop,
                    "arms": arm_results,
                }
            )
    aggregates = {}
    for arm in ("baseline", "biased"):
        positive = [row for row in rows if row["reference_contains_term"]]
        negative = [row for row in rows if not row["reference_contains_term"]]
        recalls = [
            not result["arms"][arm]["failure"]
            and bool(
                re.search(
                    rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",
                    result["arms"][arm]["hypothesis"],
                    re.I,
                )
            )
            for result in positive
        ]
        insertions = [
            not result["arms"][arm]["failure"]
            and bool(
                re.search(
                    rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",
                    result["arms"][arm]["hypothesis"],
                    re.I,
                )
            )
            for result in negative
        ]
        edits = words = 0
        for row in rows:
            measured = score(row["reference"], row["arms"][arm]["hypothesis"])
            edits += measured["normalized_edits"]
            words += measured["reference_words"]
        aggregates[arm] = {
            "positive_term_recall_count": sum(recalls),
            "positive_term_recall_denominator": len(positive),
            "negative_term_false_insertion_count": sum(insertions),
            "negative_control_denominator": len(negative),
            "normalized_edits": edits,
            "reference_words": words,
            "normalized_wer": edits / words if words else None,
            "failures": sum(row["arms"][arm]["failure"] for row in rows),
        }
    payload = {
        "schema_version": "asr_lexicon_bias_pilot_v1",
        "status": "development_pilot_not_clinical_validation",
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": manifest_digest,
        "dataset_lock_sha256": _sha256_file(lock_path),
        "profile_id": profile.profile_id,
        "profile_sha256": profile.sha256,
        "lexicon_sha256": _sha256_file(lexicon_path),
        "evaluation_code_sha256": _sha256_file(__file__),
        "adapter_code_sha256": _sha256_file(Path(__file__).with_name("adapter.py")),
        "biasing_code_sha256": _sha256_file(
            Path(__file__).with_name("context_biasing.py")
        ),
        "term": term,
        "candidate_bias_metadata": bias,
        "acceptance_data_used": False,
        "clinical_gold": False,
        "paired_sample_count": len(rows),
        "selection": "one clean positive turn and nearest non-target reference turn per eligible foreground; 250 ms crop padding",
        "limitations": [
            "Upstream mock references are not adjudicated clinical gold.",
            "The term-positive and negative-control window subset is small and selected from development references.",
            "No model profile admission or clinical safety claim follows from this pilot.",
        ],
        "aggregates": aggregates,
        "samples": rows,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="evaluation/datasets/meddistract-detailed-v1/manifest.json",
    )
    parser.add_argument("--audio-root", default="data/datasets/meddistract-detailed-v1")
    parser.add_argument(
        "--profile", default="evaluation/expanded-whisper-profiles.json"
    )
    parser.add_argument(
        "--lexicon", default="evaluation/lexicons/clinical-english-v1-e01.json"
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = evaluate_bias(
        args.manifest, args.audio_root, args.profile, args.lexicon, args.out
    )
    print(json.dumps(report["aggregates"], indent=2))
