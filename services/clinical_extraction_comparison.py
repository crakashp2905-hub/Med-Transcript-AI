"""Local-only deterministic/Qwen clinical extraction comparison on existing data."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from services.review.clinical_models import LocalClinicalModels, RuleExtractor


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evaluation/datasets/meddistract-detailed-v1/manifest.json"


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def source_transcript(case):
    turns = case.get("reference_turns")
    if not isinstance(turns, list) or not turns:
        raise ValueError("clinical_comparison_reference_turns_required")
    segments = []
    for index, turn in enumerate(turns):
        text = re.sub(r"<[^>]*>", "", turn.get("reference", ""))
        if not text.strip():
            continue
        role = {"doctor": "clinician", "patient": "patient"}.get(
            turn.get("role"), "unknown"
        )
        start_ms = int(turn.get("start_ms", 0))
        end_ms = int(turn.get("end_ms", start_ms + 1))
        segment_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{case['group_id']}:turn:{index}:{start_ms}:{end_ms}:{role}:{text}",
            )
        )
        segments.append(
            {
                "segment_id": segment_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "role": role,
                "text": text,
            }
        )
    if not segments:
        raise ValueError("clinical_comparison_no_nonempty_reference_turns")
    return {"segments": segments}


def fact_signature(fact):
    evidence = fact.get("evidence") or {}
    return (
        evidence.get("segment_id"),
        evidence.get("start_char"),
        evidence.get("end_char"),
        evidence.get("quote"),
        fact.get("category"),
        fact.get("subject"),
        fact.get("assertion"),
        fact.get("temporality"),
    )


def fact_summary(facts, transcript):
    segments = {segment["segment_id"]: segment for segment in transcript["segments"]}
    categories = Counter()
    span_digests = []
    source_span_valid = 0
    for fact in facts:
        categories[fact.get("category", "unknown")] += 1
        evidence = fact.get("evidence") or {}
        segment = segments.get(str(evidence.get("segment_id")))
        quote = evidence.get("quote")
        start, end = evidence.get("start_char"), evidence.get("end_char")
        if (
            segment
            and isinstance(start, int)
            and isinstance(end, int)
            and 0 <= start < end <= len(segment["text"])
            and segment["text"][start:end] == quote
        ):
            source_span_valid += 1
            span_digests.append(
                digest(
                    {
                        "segment_id": evidence["segment_id"],
                        "start_char": start,
                        "end_char": end,
                        "quote": quote,
                    }
                )
            )
        else:
            span_digests.append(None)
    return {
        "fact_count": len(facts),
        "category_counts": dict(sorted(categories.items())),
        "valid_evidence_span_count": source_span_valid,
        "invalid_evidence_span_count": len(facts) - source_span_valid,
        "evidence_span_sha256": span_digests,
        "all_unreviewed": bool(facts)
        and all(
            fact.get("reviewed") is False and fact.get("critical_reviewed") is False
            for fact in facts
        ),
        "fact_set_sha256": digest([fact_signature(fact) for fact in facts]),
    }


def compare_transcript(
    transcript, *, case_id, dataset_info, provider=None, batch_size=20
):
    if not 1 <= batch_size <= 20:
        raise ValueError("clinical_comparison_batch_size_out_of_range")
    baseline = RuleExtractor().extract_facts(
        transcript, authorized=True, synthetic=True
    )["facts"]
    provider = provider or LocalClinicalModels(enabled=True)
    model_facts = []
    findings = []
    calls = []
    failed_batches = []
    batches = [
        transcript["segments"][start : start + batch_size]
        for start in range(0, len(transcript["segments"]), batch_size)
    ]
    for index, segments in enumerate(batches):
        try:
            result = provider.extract_facts(
                {"segments": segments}, authorized=True, synthetic=True
            )
            model_facts.extend(result.get("facts", []))
            findings.extend(result.get("findings", []))
            calls.append(result.get("provenance", {}))
        except Exception as exc:
            code = getattr(exc, "code", None)
            failed_batches.append(
                {
                    "batch_index": index,
                    "segment_count": len(segments),
                    "failure_code": code
                    if isinstance(code, str)
                    else "clinical_model_batch_failed",
                }
            )

    baseline_summary = fact_summary(baseline, transcript)
    model_summary = fact_summary(model_facts, transcript)
    direct_model_facts = [
        fact
        for fact in model_facts
        if fact.get("extraction_version") != "source_span_fallback_after_model_v1"
    ]
    baseline_spans = Counter(fact_signature(fact) for fact in baseline)
    direct_spans = Counter(fact_signature(fact) for fact in direct_model_facts)
    exact_agreement = sum((baseline_spans & direct_spans).values())
    usage = Counter()
    for call in calls:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = call.get("usage", {}).get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                usage[key] += value
    manifest_info = dataset_info.get("manifest_sha256")
    source_hash = digest(transcript)
    return {
        "schema_version": "clinical_extraction_comparison_v1",
        "case_id": case_id,
        "dataset": dataset_info,
        "transcript_sha256": source_hash,
        "segment_count": len(transcript["segments"]),
        "batch_size": batch_size,
        "batch_count": len(batches),
        "completed_batches": len(calls),
        "failed_batches": failed_batches,
        "deterministic_baseline": baseline_summary,
        "local_qwen_proposal": {
            **model_summary,
            "status": "partial_failure" if failed_batches else "complete",
            "direct_model_fact_count": len(direct_model_facts),
            "source_span_fallback_count": len(model_facts) - len(direct_model_facts),
            "model_findings_count": len(findings),
            "model_findings": [finding.get("code", "unknown") for finding in findings],
            "exact_signature_overlap_with_deterministic": exact_agreement,
            "local_calls": calls,
            "usage_totals": dict(usage),
        },
        "scope": "local_engineering_diagnostic_on_public_mock_transcript",
        "clinical_accuracy": "not_established",
        "clinical_adjudication": "not_performed",
        "provider_cost_usd": 0,
        "hardware_cost": "not_measured",
        "clinical_release_authorized": False,
        "manifest_sha256_bound": bool(manifest_info),
    }


def load_case(manifest_path, case_id):
    manifest_path = Path(manifest_path).resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    case = next((row for row in manifest["cases"] if row["group_id"] == case_id), None)
    if case is None:
        raise ValueError("clinical_comparison_case_not_in_manifest")
    dataset_info = {
        "dataset_id": manifest["dataset_id"],
        "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_revision": manifest["source_revision"],
        "license": manifest["license"],
        "case_id": case_id,
        "audio_sha256": case["audio_sha256"],
        "condition": case["condition"],
        "split": manifest["split"],
    }
    return source_transcript(case), dataset_info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", default="day1_consultation07__clean")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    transcript, info = load_case(args.manifest, args.case_id)
    report = compare_transcript(
        transcript, case_id=args.case_id, dataset_info=info, batch_size=args.batch_size
    )
    output = args.output
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    print(
        json.dumps(
            {
                "output": output.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "batches": report["completed_batches"],
                "failed_batches": len(report["failed_batches"]),
            }
        )
    )


if __name__ == "__main__":
    main()
