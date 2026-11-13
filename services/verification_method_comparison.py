"""Reconcile frozen verification arms and measure evidence-graph provenance only."""

import hashlib
import json
import platform
from pathlib import Path

from services.evidence_graph import validate_proposal
from services.review.clinical import check_claim


def _confusion(rows, field):
    safe_controls = sum(not row["unsafe_reference"] for row in rows)
    false_alarms = sum(
        not row["unsafe_reference"] and row[field] is True for row in rows
    )
    return {
        "attempted": len(rows),
        "critical_misses": sum(
            row["unsafe_reference"] and row[field] is not True for row in rows
        ),
        "omission_misses": sum(
            row["category"] == "omission"
            and row["unsafe_reference"]
            and row[field] is not True
            for row in rows
        ),
        "false_alarms": false_alarms,
        "safe_controls": safe_controls,
        "false_block_rate": false_alarms / safe_controls if safe_controls else None,
        "blocks_all_cases": bool(rows) and all(row[field] is True for row in rows),
        "missing_verdicts": sum(row[field] is None for row in rows),
    }


def _failure_dimensions(rows):
    attempted = len(rows)
    return {
        "attempted": attempted,
        "model_timeouts": sum(
            row["model_failure"] == "clinical_model_timeout" for row in rows
        ),
        "model_abstentions": sum(row["model_unsafe"] is None for row in rows),
        "model_unsupported_claim_verdicts": sum(
            row["model_verdict_label"] == "unsupported" for row in rows
        ),
        "structurally_unsupported_sources": sum(
            not row["graph_provenance_valid"] for row in rows
        ),
        "structurally_unsupported_source_rate": (
            sum(not row["graph_provenance_valid"] for row in rows) / attempted
            if attempted
            else None
        ),
    }


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
        verdicts = (archived.get("model_result") or {}).get("verdicts", [])
        model_label = verdicts[0].get("label") if verdicts else None
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "unsafe_reference": case["unsafe"],
                "rules_unsafe": bool(findings),
                "model_unsafe": archived.get("model_unsafe"),
                "combined_unsafe": archived.get("combined_unsafe"),
                "model_failure": archived.get("model_failure"),
                "model_verdict_label": model_label,
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
        "summary": {
            "deterministic_rules": _confusion(rows, "rules_unsafe"),
            "frozen_local_model": _confusion(rows, "model_unsafe"),
            "frozen_combined_review_policy": _confusion(rows, "combined_unsafe"),
            "evidence_graph": {
                "attempted": len(rows),
                "valid_provenance_links": sum(
                    row["graph_provenance_valid"] for row in rows
                ),
                "clinical_verdicts": 0,
            },
            "failure_dimensions": _failure_dimensions(rows),
            "per_category": {
                category: {
                    "deterministic_rules": _confusion(group, "rules_unsafe"),
                    "frozen_local_model": _confusion(group, "model_unsafe"),
                    "frozen_combined_review_policy": _confusion(
                        group, "combined_unsafe"
                    ),
                    "failure_dimensions": _failure_dimensions(group),
                }
                for category in sorted({row["category"] for row in rows})
                for group in [[row for row in rows if row["category"] == category]]
            },
            "anti_overblocking_guard": {
                "methods_blocking_every_case": [
                    method
                    for method, values in (
                        ("deterministic_rules", _confusion(rows, "rules_unsafe")),
                        ("frozen_local_model", _confusion(rows, "model_unsafe")),
                        (
                            "frozen_combined_review_policy",
                            _confusion(rows, "combined_unsafe"),
                        ),
                    )
                    if values["blocks_all_cases"]
                ],
                "any_method_blocks_every_case": any(
                    _confusion(rows, field)["blocks_all_cases"]
                    for field in ("rules_unsafe", "model_unsafe", "combined_unsafe")
                ),
                "interpretation": "Flag for review; no method earns acceptance by blocking every case.",
            },
        },
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
        "source_hashes": {
            name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
            for name in (
                "services/verification_method_comparison.py",
                "services/evidence_graph.py",
                "services/review/clinical.py",
                "tests/test_verification_method_comparison.py",
            )
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "model_inference": "none; frozen report reused",
        },
        "limitations": [
            "Cases are developer-authored and not independent clinical gold.",
            "Model arm is reused from an earlier local run; no model was called by this report.",
            "Evidence-graph validation cannot detect semantic mismatch when citations themselves are structurally valid.",
        ],
    }
    report["runtime_sha256"] = hashlib.sha256(
        json.dumps(report["runtime"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    Path(output_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
