"""Offline ASR benchmark harness. Failed samples remain in the scoring denominator."""

import argparse
import json
import re
import time
from pathlib import Path
from uuid import uuid4

from services.api.ingest import file_sha256, inspect_pcm_wav
from services.asr.adapter import ASRFailure, FasterWhisperAdapter
from services.asr.profiles import load_profiles
from services.asr.transcripts import build_transcript


def tokens(text, normalized=True):
    if not normalized:
        return text.split()
    # Keep decimals, unit words and negation; do not equate 0.5 with 5 or mg with mcg.
    return re.findall(r"\d+(?:\.\d+)?|[a-z]+(?:['-][a-z]+)*", text.lower())


def distance(reference, hypothesis):
    previous = list(range(len(hypothesis)+1))
    for index, left in enumerate(reference, 1):
        current = [index]
        for column, right in enumerate(hypothesis, 1):
            current.append(min(current[-1]+1, previous[column]+1, previous[column-1]+(left != right)))
        previous = current
    return previous[-1]


def score(reference, hypothesis):
    reference_tokens, hypothesis_tokens = tokens(reference), tokens(hypothesis)
    if len(reference_tokens) > 10000 or len(hypothesis_tokens) > 10000:
        raise ValueError("Scoring token limit exceeded")
    return {"reference_words": len(reference_tokens), "hypothesis_words": len(hypothesis_tokens),
            "normalized_edits": distance(reference_tokens, hypothesis_tokens),
            "raw_edits": distance(tokens(reference, False), tokens(hypothesis, False)),
            "raw_reference_words": len(tokens(reference, False))}


def run(manifest_path, profile, output_path, retain_hypotheses=False):
    source = Path(manifest_path).resolve()
    manifest = json.loads(source.read_text(encoding="utf-8"))
    if manifest.get("data_class") not in ("synthetic", "approved_public") or not manifest.get("rights_reviewed"):
        raise ValueError("This harness accepts rights-reviewed synthetic or public evaluation material only")
    samples = manifest.get("samples", [])
    if not samples or len(samples)>10000 or len({item["sample_id"] for item in samples}) != len(samples):
        raise ValueError("Use 1–10000 uniquely identified samples")
    profile.verify_artifacts()
    rows, total_words, total_edits, raw_words, raw_edits, failures = [], 0, 0, 0, 0, 0
    adapter = FasterWhisperAdapter(profile)
    for sample in samples:
        started, hypothesis, error = time.perf_counter(), "", None
        audio = (source.parent / sample["audio"]).resolve()
        if not audio.is_relative_to(source.parent):
            raise ValueError("Evaluation audio must be inside the manifest directory")
        try:
            if sample.get("language") != "en" or file_sha256(audio) != sample["audio_sha256"]:
                raise ASRFailure("asset_integrity_failure")
            metadata = inspect_pcm_wav(audio)
            metadata["sha256"] = sample["audio_sha256"]
            raw = adapter.transcribe(audio, metadata, lambda: None)
            transcript = build_transcript(raw, metadata, "synthetic-evaluation", sample["sample_id"], profile, str(uuid4()), 1)
            hypothesis = " ".join(segment["text"].strip() for segment in transcript["segments"])
        except ASRFailure as exc:
            error = exc.code
        except Exception:
            error = "evaluation_sample_failed"
        if error:
            failures += 1
        metrics = score(sample["reference"], hypothesis)
        total_words += metrics["reference_words"]
        total_edits += metrics["normalized_edits"]
        raw_words += metrics["raw_reference_words"]
        raw_edits += metrics["raw_edits"]
        row = {"sample_id": sample["sample_id"], "group_id": sample["group_id"], "status": "failed" if error else "completed",
               "error_code": error, "elapsed_seconds": round(time.perf_counter()-started, 4), **metrics}
        if retain_hypotheses:
            row.update(reference=sample["reference"], hypothesis=hypothesis)
        rows.append(row)
    report = {"schema_version": "1.0", "dataset_id": manifest["dataset_id"], "split_role": manifest["split_role"],
        "data_class": manifest["data_class"], "profile_id": profile.profile_id, "profile_sha256": profile.sha256,
        "model_revision": profile.revision, "scoring_profile": "lowercase_words_preserve_decimals_units_negation_v1",
        "sample_count": len(rows), "failed_samples": failures, "reference_words": total_words,
        "normalized_edits": total_edits, "normalized_wer": total_edits/total_words if total_words else None,
        "raw_wer": raw_edits/raw_words if raw_words else None,
        "failure_policy": "empty_hypothesis_full_reference_deletions", "critical_error_adjudication": "pending_clinician_review",
        "clinical_release_gate": "not_evaluated", "samples": rows}
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {key: value for key, value in report.items() if key != "samples"}


def main():
    parser = argparse.ArgumentParser(description="Offline English ASR evaluation with explicit input rights and failure denominators")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--out", default="data/evaluation-results.json")
    parser.add_argument("--retain-hypotheses", action="store_true")
    args = parser.parse_args()
    profile = load_profiles(args.profiles).get(args.profile_id)
    if profile is None:
        parser.error("Profile ID not present in the configured file")
    print(json.dumps(run(args.manifest, profile, args.out, args.retain_hypotheses)))


if __name__ == "__main__":
    main()
