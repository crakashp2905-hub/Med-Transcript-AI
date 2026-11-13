"""Reconcile frozen verification arms and measure evidence-graph provenance only."""

import hashlib
import json
from pathlib import Path

from services.evidence_graph import validate_proposal
from services.review.clinical import check_claim


def compare(challenge_path, frozen_path, output_path, *, source_commit):
    challenge_bytes = Path(challenge_path).read_bytes()
    frozen_bytes = Path(frozen_path).read_bytes()
    challenge = json.loads(challenge_bytes)
    frozen = json.loads(frozen_bytes)
    if Path(output_path).exists():
        raise ValueError("preserve_previous_evidence_choose_new_report")
    expected_hash = hashlib.sha256(challenge_bytes).hexdigest()
    if frozen.get("challenge_sha256") != expected_hash:
        raise ValueError("frozen_results_challenge_mismatch")
    frozen_cases = {row["id"]: row for row in frozen.get("cases", [])}
    cases = challenge["cases"]
    if len(frozen_cases) != len(frozen.get("cases", [])) or set(frozen_cases) != {
        row["id"] for row in cases
    }:
        raise ValueError("frozen_results_case_set_mismatch")

    rows = []
    for case in cases:
        archived = frozen_cases[case["id"]]
        # This graph checks source IDs, quote offsets, and citation edges. It does
        # not connect claim semantics to evidence and cannot judge clinical truth.
        transcript = {
            "id": "dev-" + case["id"],
            "audio_asset_id": "synthetic-audio-" + case["id"],
            "segments": [{"segment_id": "segment-1", "text": case["source"]}],
        }
        fact = {
            "fact_id": "fact-" + case["id"],
            "evidence": {
                "segment_id": "segment-1",
                "start_char": 0,
                "end_char": len(case["source"]),
                "quote": case["source"],
            },
        }
        graph = validate_proposal(transcript, [fact])
        findings = check_claim(case["source"], case["claim"])
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "unsafe_reference": case["unsafe"],
                "rules_unsafe": bool(findings),
                "model_unsafe": archived.get("model_unsafe"),
                "combined_unsafe": archived.get("combined_unsafe"),
                "model_failure": archived.get("model_failure"),
                "graph_provenance_valid": graph["complete_to_fact"],
                "graph_semantic_verdict": None,
                "graph_scope": "citation_structure_only_not_clinical_detection",
                "edge_count": len(graph["edges"]),
            }
        )

    report = {
        "schema_version": "verification_methods_reconciled_v1",
        "source_commit": source_commit,
        "challenge_sha256": expected_hash,
        "frozen_model_report_sha256": hashlib.sha256(frozen_bytes).hexdigest(),
        "reference_status": challenge["scope"],
        "model_results_reused_without_inference": True,
        "clinical_acceptance": False,
        "cannot_clear_approval_gates": True,
        "methods": [
            "deterministic_rules",
            "frozen_local_model",
            "combined_review_policy",
            "evidence_graph_provenance",
        ],
        "cases": rows,
        "graph_summary": {
            "attempted": len(rows),
            "valid_provenance_links": sum(
                row["graph_provenance_valid"] for row in rows
            ),
            "invalid_provenance_links": sum(
                not row["graph_provenance_valid"] for row in rows
            ),
            "clinical_verdicts": 0,
            "interpretation": "Graph validity is a source-link invariant, not an unsafe-claim classifier.",
        },
        "frozen_model_summary": frozen.get("summary", {}).get("model"),
        "frozen_combined_summary": frozen.get("summary", {}).get(
            "combined_review_policy"
        ),
        "limitations": [
            "Cases are developer-authored and not independent clinical gold.",
            "Model arm is reused from an earlier local run; no model was called by this report.",
            "Evidence-graph validation cannot detect semantic mismatch when citations themselves are structurally valid.",
        ],
    }
    Path(output_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
