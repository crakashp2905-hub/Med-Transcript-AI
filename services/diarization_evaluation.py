"""Full-recording diarization against upstream turn labels, not clinical gold."""

import argparse
import itertools
import json
import time
from pathlib import Path

from services.diarization import diarize


def score_turns(
    reference,
    predicted,
    *,
    collar_ms=0,
    overlap_policy="score_all",
):
    if type(collar_ms) is not int or collar_ms < 0:
        raise ValueError("invalid_diarization_collar")
    if overlap_policy not in {"score_all", "ignore_reference_overlap"}:
        raise ValueError("invalid_diarization_overlap_policy")
    refs = sorted({r["role"] for r in reference})
    hyps = sorted(
        {r["speaker_id"] for r in predicted if r.get("speaker_id") is not None}
    )
    if len(refs) > 4 or len(hyps) > 100:
        raise ValueError("Development scorer assignment budget exceeded")
    base_boundaries = {
        x[k] for x in reference + predicted for k in ("start_ms", "end_ms")
    }
    if reference and collar_ms:
        ref_start = min(r["start_ms"] for r in reference)
        ref_end = max(r["end_ms"] for r in reference)
        change_boundaries = {
            point
            for r in reference
            for point in (r["start_ms"], r["end_ms"])
            if ref_start < point < ref_end
        }
        for point in change_boundaries:
            base_boundaries.add(max(ref_start, point - collar_ms))
            base_boundaries.add(min(ref_end, point + collar_ms))
    boundaries = sorted(base_boundaries)
    intervals = []
    intersections = {(r, h): 0 for r in refs for h in hyps}
    ignored_collar_ms = ignored_overlap_ms = 0
    ref_start = min((r["start_ms"] for r in reference), default=0)
    ref_end = max((r["end_ms"] for r in reference), default=0)
    change_boundaries = {
        point
        for r in reference
        for point in (r["start_ms"], r["end_ms"])
        if ref_start < point < ref_end
    }
    for a, b in zip(boundaries, boundaries[1:]):
        rs = {r["role"] for r in reference if r["start_ms"] < b and r["end_ms"] > a}
        hs = {
            r["speaker_id"]
            for r in predicted
            if r.get("speaker_id") is not None and r["start_ms"] < b and r["end_ms"] > a
        }
        midpoint = (a + b) / 2
        if collar_ms and any(
            abs(midpoint - point) < collar_ms for point in change_boundaries
        ):
            ignored_collar_ms += b - a
            continue
        if overlap_policy == "ignore_reference_overlap" and len(rs) > 1:
            ignored_overlap_ms += b - a
            continue
        intervals.append((b - a, rs, hs))
        for r in rs:
            for h in hs:
                intersections[r, h] += b - a
    # One-to-one global optimal mapping; anonymous clusters never imply clinical roles.
    padded = hyps + [f"__missing_{i}" for i in range(max(0, len(refs) - len(hyps)))]
    assignment = max(
        itertools.permutations(padded, len(refs)),
        key=lambda hs: sum(intersections.get((r, h), 0) for r, h in zip(refs, hs)),
        default=(),
    )
    mapping = {h: r for r, h in zip(refs, assignment)}
    total = miss = false = confusion = 0
    reference_ms = {r: 0 for r in refs}
    predicted_ms = {h: 0 for h in hyps}
    speaker_intersections = {(r, h): 0 for r in refs for h in hyps}
    for ms, rs, hs in intervals:
        total += len(rs) * ms
        miss += max(0, len(rs) - len(hs)) * ms
        false += max(0, len(hs) - len(rs)) * ms
        correct = sum(mapping.get(h) in rs for h in hs)
        confusion += (min(len(rs), len(hs)) - correct) * ms
        for role in rs:
            reference_ms[role] += ms
            for speaker in hs:
                speaker_intersections[role, speaker] += ms
        for speaker in hs:
            predicted_ms[speaker] += ms
    assigned = {role: speaker for speaker, role in mapping.items() if speaker in hyps}
    per_reference_speaker_jer = {}
    for role in refs:
        speaker = assigned.get(role)
        intersection = speaker_intersections.get((role, speaker), 0) if speaker else 0
        hypothesis_ms = predicted_ms.get(speaker, 0) if speaker else 0
        union = reference_ms[role] + hypothesis_ms - intersection
        per_reference_speaker_jer[role] = (
            1 - intersection / union if union else None
        )
    jer_values = [value for value in per_reference_speaker_jer.values() if value is not None]
    return {
        "reference_speaker_ms": total,
        "missed_speaker_ms": miss,
        "false_alarm_speaker_ms": false,
        "confused_speaker_ms": confusion,
        "diarization_error_rate": (miss + false + confusion) / total if total else None,
        "speaker_jaccard_error_rate": (
            sum(jer_values) / len(jer_values) if jer_values else None
        ),
        "per_reference_speaker_jer": per_reference_speaker_jer,
        "collar_ms": collar_ms,
        "overlap_policy": overlap_policy,
        "ignored_collar_ms": ignored_collar_ms,
        "ignored_reference_overlap_ms": ignored_overlap_ms,
        "overlap_scored": True,
        "optimal_scoring_mapping": mapping,
        "predicted_clusters": len(hyps),
        "reference_speakers": len(refs),
        "reference_status": "upstream_TextGrid_turn_labels_not_independently_adjudicated",
        "scoring_mapping_is_not_clinician_role_confirmation": True,
    }


def separate_workload_metrics(score, *, overlap_error_ms=0, role_confirmation_turns=0):
    """Keep acoustic error measures separate from clinician confirmation work."""
    return {
        **{
            key: score.get(key)
            for key in (
                "diarization_error_rate",
                "missed_speaker_ms",
                "false_alarm_speaker_ms",
                "confused_speaker_ms",
            )
        },
        "overlap_error_ms": overlap_error_ms,
        "role_confirmation_turns": role_confirmation_turns,
        "clinical_role_accuracy": None,
    }


def run(manifest_path, model_path, output, threshold=None):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    if threshold is not None:
        model["clustering_threshold"] = threshold
    report = {
        "dataset_id": manifest["dataset_id"],
        "data_class": "approved_public_mock",
        "model": model,
        "clinical_acceptance": False,
        "cases": [],
    }
    for case in manifest["cases"]:
        audio = Path("data/datasets/primock57-full-v1") / case["audio"]
        from services.api.ingest import file_sha256

        if file_sha256(audio) != case["audio_sha256"]:
            raise ValueError("Source audio hash mismatch")
        start = time.perf_counter()
        try:
            result = diarize(audio, model)
            row = {
                "id": case["group_id"],
                "failed": False,
                "duration_ms": case["duration_ms"],
                "metrics": score_turns(case["reference_turns"], result["segments"]),
                "result": result,
            }
        except Exception as e:
            row = {
                "id": case["group_id"],
                "failed": True,
                "error_type": type(e).__name__,
            }
        row["wall_seconds"] = time.perf_counter() - start
        report["cases"].append(row)
        Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in row.items() if k != "result"}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--manifest", default="evaluation/datasets/primock57-full-v1/manifest.json"
    )
    p.add_argument("--model", default="data/models/public-diarization-v1/manifest.json")
    p.add_argument(
        "--output", default="evaluation/reports/public-diarization-2026-10-25.json"
    )
    p.add_argument("--threshold", type=float)
    a = p.parse_args()
    run(a.manifest, a.model, a.output, a.threshold)
