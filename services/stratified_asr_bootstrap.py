"""Paired consultation-cluster uncertainty by condition, role, and literal term."""

import argparse
import hashlib
import json
import random
import re
import subprocess
from pathlib import Path

from services.detailed_benchmark import fast_score
from services.conversation_experiment import TERMS, term_counts
from services.immutable_reports import publish_json_once
from services.paired_asr_bootstrap import _percentile


DEFAULT_MANIFEST = Path("evaluation/datasets/meddistract-detailed-v1/manifest.json")
DEFAULT_PAIRED = Path("evaluation/reports/paired-asr-bootstrap-v1.json")
DEFAULT_TAXONOMY = Path("evaluation/reports/error-taxonomy-v2/report.json")
DEFAULT_OUTPUT = Path("evaluation/reports/paired-asr-stratified-bootstrap-v1.json")
ITERATIONS = 10000
SEED = 20261121


def _sha_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _paired_interval(group_metrics, *, numerator_key, denominator_key, seed):
    groups = sorted(group_metrics)
    if not groups:
        return None
    conditions = ("clean", "distracted")
    for group in groups:
        if set(group_metrics[group]) != set(conditions):
            raise ValueError("stratified_clean_distracted_group_pair_required")
        for condition in conditions:
            if group_metrics[group][condition][denominator_key] <= 0:
                raise ValueError("stratified_positive_reference_denominator_required")

    def aggregate(selected, condition):
        numerator = sum(
            group_metrics[group][condition][numerator_key] for group in selected
        )
        denominator = sum(
            group_metrics[group][condition][denominator_key] for group in selected
        )
        return numerator / denominator

    clean = aggregate(groups, "clean")
    distracted = aggregate(groups, "distracted")
    if len(groups) < 2:
        return {
            "clean_rate": clean,
            "distracted_rate": distracted,
            "distracted_minus_clean": distracted - clean,
            "confidence_level": 0.95,
            "interval_method": "not_estimable_fewer_than_two_consultation_groups",
            "iterations": ITERATIONS,
            "seed": seed,
            "low": None,
            "high": None,
            "consultation_groups": len(groups),
            "paired_groups": groups,
        }
    rng = random.Random(seed)
    deltas = []
    for _ in range(ITERATIONS):
        selected = rng.choices(groups, k=len(groups))
        deltas.append(aggregate(selected, "distracted") - aggregate(selected, "clean"))
    deltas.sort()
    return {
        "clean_rate": clean,
        "distracted_rate": distracted,
        "distracted_minus_clean": distracted - clean,
        "confidence_level": 0.95,
        "interval_method": "percentile_consultation_cluster_bootstrap",
        "iterations": ITERATIONS,
        "seed": seed,
        "low": _percentile(deltas, 0.025),
        "high": _percentile(deltas, 0.975),
        "consultation_groups": len(groups),
        "paired_groups": groups,
    }


def _case_reference(source):
    return " ".join(
        re.sub(r"<[^>]+>", "", turn["reference"]) for turn in source["reference_turns"]
    )


def _validate_sources(manifest_path, paired_path, taxonomy_path):
    manifest_bytes = manifest_path.read_bytes()
    paired_bytes = paired_path.read_bytes()
    taxonomy_bytes = taxonomy_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    paired = json.loads(paired_bytes)
    taxonomy = json.loads(taxonomy_bytes)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if (
        manifest.get("rights_reviewed") is not True
        or manifest.get("data_class") != "approved_public"
        or paired.get("manifest_sha256") != manifest_hash
        or taxonomy.get("manifest_sha256") != manifest_hash
    ):
        raise ValueError("source_manifest_provenance_mismatch")
    lock = json.loads((manifest_path.parent / "lock.json").read_text(encoding="utf-8"))
    if lock.get("manifest_sha256") != manifest_hash:
        raise ValueError("source_manifest_lock_mismatch")
    truth = {row["group_id"]: row for row in manifest.get("cases", [])}
    if len(truth) != len(manifest.get("cases", [])) or not truth:
        raise ValueError("source_manifest_case_set_invalid")
    taxonomy_reports = {row["path"]: row for row in taxonomy.get("reports", [])}
    candidates = []
    for candidate in paired.get("candidates", []):
        path = candidate["source_report"]
        report_path = Path(path)
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes)
        if (
            hashlib.sha256(report_bytes).hexdigest()
            != candidate["source_report_sha256"]
            or report.get("complete") is not True
            or report.get("manifest_sha256") != manifest_hash
            or report.get("mode") != "fixed"
        ):
            raise ValueError("candidate_report_integrity_or_scope_mismatch")
        taxonomy_report = taxonomy_reports.get(path)
        if (
            taxonomy_report is None
            or taxonomy_report.get("sha256") != candidate["source_report_sha256"]
            or taxonomy_report.get("complete") is not True
        ):
            raise ValueError("candidate_taxonomy_binding_missing")
        source_rows = {row["id"]: row for row in report.get("cases", [])}
        role_rows = {row["id"]: row for row in taxonomy_report.get("cases", [])}
        if set(source_rows) != set(truth) or set(role_rows) != set(truth):
            raise ValueError("candidate_case_coverage_mismatch")
        cases = {}
        for case_id, source in truth.items():
            row = source_rows[case_id]
            role = role_rows[case_id]
            reference = _case_reference(source)
            if (
                row.get("foreground_id") != source.get("foreground_id")
                or row.get("condition") != source.get("condition")
                or row.get("input_sha256") != source.get("audio_sha256")
                or row.get("reference") != reference
                or role.get("reference_sha256") != _sha_text(reference)
            ):
                raise ValueError("candidate_source_reference_binding_mismatch")
            expected = fast_score(
                reference, "" if row.get("failed") else row.get("hypothesis", "")
            )
            if any(row.get(key) != value for key, value in expected.items()):
                raise ValueError("candidate_failure_inclusive_score_mismatch")
            expected_terms = term_counts(
                reference, "" if row.get("failed") else row.get("hypothesis", "")
            )
            if row.get("term_diagnostics") != expected_terms:
                raise ValueError("candidate_term_diagnostic_mismatch")
            if bool(row.get("failed")) != bool(role.get("failed")):
                raise ValueError("taxonomy_failure_status_mismatch")
            cases[case_id] = {"source": source, "row": row, "role": role}
        candidates.append(
            {
                "candidate_id": candidate["candidate_id"],
                "source_report": path,
                "source_report_sha256": candidate["source_report_sha256"],
                "overall_recording_condition_delta": candidate["paired_bootstrap"],
                "cases": cases,
                "groups": sorted({row["foreground_id"] for row in truth.values()}),
            }
        )
    if len(candidates) != len(paired.get("candidates", [])) or not candidates:
        raise ValueError("paired_candidate_reports_required")
    return (
        manifest,
        paired,
        taxonomy,
        candidates,
        {
            "manifest_sha256": manifest_hash,
            "paired_report_sha256": hashlib.sha256(paired_bytes).hexdigest(),
            "taxonomy_report_sha256": hashlib.sha256(taxonomy_bytes).hexdigest(),
        },
    )


def _role_results(candidate, roles):
    output = {}
    for role_index, role_name in enumerate(roles):
        by_group = {}
        failed_pairs = 0
        for case in candidate["cases"].values():
            source, row, taxonomy = case["source"], case["row"], case["role"]
            role = taxonomy.get("reference_role_counts", {}).get(role_name)
            if role is None:
                continue
            group, condition = source["foreground_id"], source["condition"]
            metrics = by_group.setdefault(group, {})
            if condition in metrics:
                raise ValueError("duplicate_role_condition_case")
            edits = role["substitutions"] + role["deletions"]
            if row["failed"]:
                failed_pairs += 1
                if edits != role["reference_words"]:
                    raise ValueError("failed_role_case_not_full_reference_deletion")
            metrics[condition] = {
                "errors": edits,
                "reference_words": role["reference_words"],
            }
        output[role_name] = {
            "estimand": "substitution_plus_deletion_rate_by_reference_role; insertions_unattributed",
            "failed_cases_included": failed_pairs,
            "paired_interval": _paired_interval(
                by_group,
                numerator_key="errors",
                denominator_key="reference_words",
                seed=SEED + 100 * role_index,
            ),
        }
    return output


def _term_results(candidate, terms):
    output = {}
    for term_index, term in enumerate(terms):
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.I)
        by_group = {}
        term_cases = set()
        term_groups = set()
        failed_cases = 0
        for case in candidate["cases"].values():
            source, row = case["source"], case["row"]
            reference = _case_reference(source)
            reference_count = len(pattern.findall(reference))
            if reference_count == 0:
                continue
            group, condition = source["foreground_id"], source["condition"]
            hypothesis = "" if row["failed"] else row.get("hypothesis", "")
            hyp_count = len(pattern.findall(hypothesis))
            missing = max(0, reference_count - hyp_count)
            matched = reference_count - missing
            if row["failed"]:
                failed_cases += 1
                matched = 0
                missing = reference_count
            metrics = by_group.setdefault(group, {})
            if condition in metrics:
                raise ValueError("duplicate_term_condition_case")
            metrics[condition] = {"matched": matched, "references": reference_count}
            term_cases.add(source["group_id"])
            term_groups.add(group)
        output[term] = {
            "estimand": "literal_reference_term_occurrence_recall; not clinical concept correctness",
            "reference_bearing_cases": len(term_cases),
            "reference_bearing_consultation_groups": len(term_groups),
            "failed_reference_bearing_cases_included": failed_cases,
            "paired_interval": _paired_interval(
                by_group,
                numerator_key="matched",
                denominator_key="references",
                seed=SEED + 1000 + term_index,
            )
            if by_group
            else None,
        }
    return output


def build_stratified_report(
    manifest_path=DEFAULT_MANIFEST,
    paired_path=DEFAULT_PAIRED,
    taxonomy_path=DEFAULT_TAXONOMY,
    output_path=DEFAULT_OUTPUT,
):
    manifest_path, paired_path, taxonomy_path = map(
        Path, (manifest_path, paired_path, taxonomy_path)
    )
    manifest, paired, taxonomy, candidates, hashes = _validate_sources(
        manifest_path, paired_path, taxonomy_path
    )
    groups = sorted({row["foreground_id"] for row in manifest["cases"]})
    # The frozen term inventory comes from the saved per-case literal diagnostic.
    first_case = next(iter(candidates[0]["cases"].values()))["row"]
    term_pattern = first_case.get("term_diagnostics", {}).get("lexicon")
    if not isinstance(term_pattern, str) or term_pattern != TERMS.pattern:
        raise ValueError("frozen_literal_term_inventory_required")
    terms = term_pattern.split("(?:", 1)[1].split(")", 1)[0].split("|")
    if not terms:
        raise ValueError("frozen_literal_term_inventory_empty")

    results = []
    for candidate in candidates:
        role_names = sorted(
            {
                role
                for case in candidate["cases"].values()
                for role in case["role"].get("reference_role_counts", {})
            }
        )
        results.append(
            {
                "candidate_id": candidate["candidate_id"],
                "source_report": candidate["source_report"],
                "source_report_sha256": candidate["source_report_sha256"],
                "case_count": len(candidate["cases"]),
                "consultation_group_count": len(candidate["groups"]),
                "overall_recording_condition_delta": candidate[
                    "overall_recording_condition_delta"
                ],
                "speaker_role_strata": _role_results(candidate, role_names),
                "literal_clinical_term_strata": _term_results(candidate, terms),
            }
        )
    report = {
        "schema_version": "paired_asr_stratified_bootstrap_v1",
        "complete": True,
        "inference_executed": False,
        "analysis_only_replay": True,
        "scope": "retrospective_public_development_only",
        "source_commit": _source_commit(),
        "inputs": {
            "manifest_path": manifest_path.as_posix(),
            **hashes,
            "taxonomy_source_commit": taxonomy.get("source_commit"),
            "taxonomy_source_code_sha256": taxonomy.get("code_sha256"),
        },
        "protocol": {
            "resampling_unit": "foreground_consultation_group",
            "paired_conditions_kept_intact": ["clean", "distracted"],
            "iterations": ITERATIONS,
            "seed": SEED,
            "confidence_level": 0.95,
            "consultation_groups": groups,
            "failed_cases_included": True,
            "speaker_strata_source": "reference-turn edit attribution; predicted diarization is not measured",
            "term_strata_source": "frozen literal term diagnostic in candidate reports",
            "primary_wer_modified": False,
            "maximum_normalized_wer": 0.05,
        },
        "candidate_count": len(results),
        "candidates": results,
        "clinical_acceptance": False,
        "limitations": [
            "Eight convenience-sampled public mock consultation groups yield wide and unstable subgroup intervals.",
            "References are not clinician-adjudicated clinical gold; literal term matching does not establish concept correctness.",
            "Speaker strata attribute reference substitutions/deletions to annotated turns; insertions remain unattributed and predicted speaker accuracy is not measured.",
            "Term-bearing consultation groups alone contribute to each term-specific interval; terms absent from the reference have no term-specific recall estimate.",
            "All primary baselines and the <=5% WER admission gate remain unchanged.",
        ],
    }
    return publish_json_once(output_path, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--paired", type=Path, default=DEFAULT_PAIRED)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_stratified_report(
        args.manifest, args.paired, args.taxonomy, args.out
    )
    print(
        json.dumps(
            {
                "output": args.out.as_posix(),
                "candidate_count": report["candidate_count"],
                "consultation_groups": len(report["protocol"]["consultation_groups"]),
                "iterations": report["protocol"]["iterations"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
