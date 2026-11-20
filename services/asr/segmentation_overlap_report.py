"""Post-process saved overlap windows with the sequence-alignment stitcher."""

import hashlib
import json
import subprocess
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.segmentation_candidate_runner import _reference, validate_suite
from services.detailed_benchmark import fast_score
from services.immutable_reports import publish_json_once
from services.overlap_reassembly import stitch


def build_overlap_stitch_report(receipt_path, output_path, *, suite_path):
    suite_path, suite, _, manifest = validate_suite(suite_path)
    receipt_path = Path(receipt_path)
    source = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        source.get("schema_version") != "asr_segmentation_mode_receipt_v1"
        or source.get("complete") is not True
        or source.get("configuration", {}).get("mode") != "overlap_aware"
    ):
        raise ValueError("complete_overlap_aware_receipt_required")
    bindings = source.get("bindings", {})
    if (
        bindings.get("suite_sha256") != file_sha256(suite_path)
        or bindings.get("manifest_sha256") != suite["manifest_sha256"]
        or not isinstance(bindings.get("source_sha256"), dict)
    ):
        raise ValueError("overlap_stitch_source_receipt_mismatch")
    expected = {row["group_id"]: row for row in manifest["cases"]}
    cases = {row["group_id"]: row for row in source.get("cases", [])}
    if len(expected) != 16 or set(cases) != set(expected):
        raise ValueError("overlap_stitch_frozen_cohort_mismatch")

    output_cases = []
    exact_edits = sequence_edits = reference_words = 0
    failed_samples = fuzzy_events = 0
    for group_id, manifest_case in expected.items():
        case = cases[group_id]
        reference = _reference(manifest_case)
        reference_sha256 = hashlib.sha256(reference.encode("utf-8")).hexdigest()
        if (
            case.get("audio_sha256") != manifest_case["audio_sha256"]
            or case.get("reference_sha256") != reference_sha256
        ):
            raise ValueError("overlap_stitch_case_input_mismatch")
        exact = case.get("hypothesis")
        if not isinstance(exact, str) or (case.get("failed") and exact):
            raise ValueError("overlap_stitch_failure_policy_mismatch")
        chunks = case.get("chunks")
        if (
            not isinstance(chunks, list)
            or not chunks
            or len(chunks) != case.get("window_count")
        ):
            raise ValueError("overlap_stitch_window_outputs_incomplete")
        candidate = ""
        events = []
        for chunk in chunks:
            chunk_text = chunk.get("hypothesis")
            if not isinstance(chunk_text, str):
                raise ValueError("overlap_stitch_invalid_window_hypothesis")
            candidate, event = stitch(candidate, chunk_text)
            events.append(event)
        failed = bool(case.get("failed"))
        scored_candidate = "" if failed else candidate
        scored_exact = "" if failed else exact
        exact_score = fast_score(reference, scored_exact)
        sequence_score = fast_score(reference, scored_candidate)
        if exact_score["normalized_edits"] != case.get(
            "normalized_edits"
        ) or exact_score["reference_words"] != case.get("reference_words"):
            raise ValueError("overlap_stitch_baseline_score_mismatch")
        exact_edits += exact_score["normalized_edits"]
        sequence_edits += sequence_score["normalized_edits"]
        reference_words += exact_score["reference_words"]
        failed_samples += failed
        fuzzy_events += sum(
            event.get("method") == "experimental_filler_tolerant" for event in events
        )
        output_cases.append(
            {
                "group_id": group_id,
                "condition": case["condition"],
                "audio_sha256": case["audio_sha256"],
                "reference_sha256": reference_sha256,
                "failed": failed,
                "failure_policy": case["failure_policy"],
                "reference_words": exact_score["reference_words"],
                "exact_stitch_edits": exact_score["normalized_edits"],
                "sequence_stitch_edits": sequence_score["normalized_edits"],
                "exact_stitch_hypothesis": exact,
                "sequence_stitch_hypothesis": scored_candidate,
                "events": events,
                "audio_review_required": any(
                    event.get("requires_audio_review") is True for event in events
                ),
            }
        )

    report = {
        "schema_version": "asr_overlap_sequence_stitch_ablation_v1",
        "complete": True,
        "clinical_acceptance": False,
        "automatic_promotion": False,
        "inference_executed": False,
        "generator_source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "suite_sha256": file_sha256(suite_path),
        "manifest_sha256": suite["manifest_sha256"],
        "source_receipt_path": receipt_path.as_posix(),
        "source_receipt_sha256": file_sha256(receipt_path),
        "source_receipt_commit": source.get("source_commit"),
        "source_execution_sha256": bindings["source_sha256"],
        "candidate_id": source["configuration"]["candidate_id"],
        "profile_sha256": source["configuration"]["profile_sha256"],
        "case_count": len(output_cases),
        "reference_words": reference_words,
        "failed_samples": failed_samples,
        "wer_admission_maximum": 0.05,
        "arms": {
            "exact_stitch": {
                "normalized_edits": exact_edits,
                "normalized_wer": exact_edits / reference_words,
                "wer_admission": "pass"
                if exact_edits / reference_words <= 0.05
                else "fail",
            },
            "sequence_alignment_stitch": {
                "normalized_edits": sequence_edits,
                "normalized_wer": sequence_edits / reference_words,
                "wer_admission": "pass"
                if sequence_edits / reference_words <= 0.05
                else "fail",
                "fuzzy_events_requiring_audio_review": fuzzy_events,
            },
        },
        "cases": output_cases,
        "limitations": [
            "This is post-processing of the same saved window hypotheses; no ASR inference was rerun.",
            "Fuzzy overlap removals require source-audio review because repeated speech can resemble duplicated overlap.",
            "All scores are development-only and both arms remain subject to the unchanged 5% WER admission gate.",
        ],
    }
    return publish_json_once(output_path, report)
