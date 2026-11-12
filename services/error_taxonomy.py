"""Deterministic exact edit traceback over saved public-mock hypotheses only."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone
import zipfile

from services.benchmark_integrity import replay
from services.canonical import content_sha256
from services.clinical_metrics import character_distance
from services.engineering_status import sha256
from services.evaluation import tokens


def alignment(reference, hypothesis):
    """Myers column bit-vectors retain exact DP values for deterministic traceback."""
    if max(len(reference), len(hypothesis)) > 10000:
        raise ValueError("alignment_token_limit")
    masks = {}
    for i, token in enumerate(reference):
        masks[token] = masks.get(token, 0) | (1 << i)
    positive, negative = ~0, 0
    states = [(positive, negative)]
    for token in hypothesis:
        equal = masks.get(token, 0)
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        plus, minus = negative | ~(horizontal | positive), positive & horizontal
        plus, minus = (plus << 1) | 1, minus << 1
        positive, negative = minus | ~(vertical | plus), plus & vertical
        states.append((positive, negative))

    def distance(i, j):
        positive, negative = states[j]
        mask = (1 << i) - 1
        return j + (positive & mask).bit_count() - (negative & mask).bit_count()

    i, j, result = len(reference), len(hypothesis), []
    while i or j:
        current = distance(i, j)
        if (
            i
            and j
            and reference[i - 1] == hypothesis[j - 1]
            and current == distance(i - 1, j - 1)
        ):
            result.append(("match", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i and j and current == distance(i - 1, j - 1) + 1:
            result.append(("substitution", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i and current == distance(i - 1, j) + 1:
            result.append(("deletion", i - 1, None))
            i -= 1
        elif j and current == distance(i, j - 1) + 1:
            result.append(("insertion", None, j - 1))
            j -= 1
        else:
            raise ValueError("alignment_traceback_inconsistent")
    return list(reversed(result))


def reference_regions(case):
    turns = case["reference_turns"]
    regions = []
    for turn in turns:
        overlap = any(
            other["role"] != turn["role"]
            and other["start_ms"] < turn["end_ms"]
            and other["end_ms"] > turn["start_ms"]
            for other in turns
        )
        row = {
            "reference_role": "clinician" if turn["role"] == "doctor" else turn["role"],
            "uncertain_reference_turn": bool(turn.get("uncertain_reference")),
            "overlapping_reference_turn": overlap,
            "start_ms": turn["start_ms"],
            "end_ms": turn["end_ms"],
        }
        regions.extend([row] * len(tokens(re.sub(r"<[^>]+>", "", turn["reference"]))))
    return regions


def analyze(row, case):
    reference, hypothesis = tokens(row["reference"]), tokens(row["hypothesis"])
    regions = reference_regions(case)
    if len(regions) != len(reference):
        raise ValueError("reference_region_token_count_changed")
    operations = alignment(reference, hypothesis)
    counts = Counter(op for op, _, _ in operations)
    edits = sum(counts[k] for k in ("substitution", "deletion", "insertion"))
    if edits != row["normalized_edits"]:
        raise ValueError("alignment_does_not_match_frozen_score")
    ref_chars, hyp_chars = " ".join(reference), " ".join(hypothesis)
    raw_cer = character_distance(row["reference"], row["hypothesis"])
    normal_cer = character_distance(ref_chars, hyp_chars)
    summary = {
        "id": row["id"],
        "failed": row["failed"],
        "reference_words": len(reference),
        "normalized_edits": edits,
        "normalized_wer": edits / len(reference) if reference else None,
        "raw_word_edits": row["raw_edits"],
        "raw_reference_words": row["raw_reference_words"],
        "raw_wer": row["raw_edits"] / row["raw_reference_words"]
        if row["raw_reference_words"]
        else None,
        "raw_character_edits": raw_cer,
        "raw_reference_characters": len(row["reference"]),
        "raw_cer": raw_cer / len(row["reference"]) if row["reference"] else None,
        "normalized_character_edits": normal_cer,
        "normalized_reference_characters": len(ref_chars),
        "normalized_cer": normal_cer / len(ref_chars) if ref_chars else None,
        "operations": dict(counts),
        "reference_role_counts": {},
        "reference_sha256": hashlib.sha256(row["reference"].encode()).hexdigest(),
        "hypothesis_sha256": hashlib.sha256(row["hypothesis"].encode()).hexdigest(),
    }
    summary["reference_buckets"] = {
        name: {
            "reference_words": sum(bool(r[field]) for r in regions),
            "substitutions_and_deletions": 0,
        }
        for name, field in [
            ("uncertain_turn", "uncertain_reference_turn"),
            ("overlapping_turn", "overlapping_reference_turn"),
        ]
    }
    for region in regions:
        role = region["reference_role"]
        summary["reference_role_counts"].setdefault(
            role, {"reference_words": 0, "substitutions": 0, "deletions": 0}
        )["reference_words"] += 1
    errors = []
    for op, i, j in operations:
        if op == "match":
            continue
        meta = (
            regions[i]
            if i is not None
            else {
                "reference_role": "unattributed_insertion",
                "uncertain_reference_turn": None,
                "overlapping_reference_turn": None,
                "start_ms": None,
                "end_ms": None,
            }
        )
        left, right = (
            reference[i] if i is not None else "",
            hypothesis[j] if j is not None else "",
        )
        tags = []
        if left in ("um", "uh", "erm", "hmm"):
            tags.append("reference_disfluency")
        if meta["uncertain_reference_turn"]:
            tags.append("uncertain_reference_turn")
        if meta["overlapping_reference_turn"]:
            tags.append("overlapping_reference_turn")
        if i is not None and j is not None:
            if (j + 1 < len(hypothesis) and left == right + hypothesis[j + 1]) or (
                i + 1 < len(reference) and left + reference[i + 1] == right
            ):
                tags.append("possible_token_split_or_merge")
        if i is not None and op in ("substitution", "deletion"):
            summary["reference_role_counts"][meta["reference_role"]][
                "substitutions" if op == "substitution" else "deletions"
            ] += 1
            for name, field in [
                ("uncertain_turn", "uncertain_reference_turn"),
                ("overlapping_turn", "overlapping_reference_turn"),
            ]:
                if meta[field]:
                    summary["reference_buckets"][name][
                        "substitutions_and_deletions"
                    ] += 1
        errors.append(
            {
                "operation": op,
                "reference_index": i,
                "hypothesis_index": j,
                "reference_token": left,
                "hypothesis_token": right,
                **meta,
                "diagnostic_tags": ";".join(tags),
            }
        )
    summary["predicted_speaker_accuracy_measured"] = False
    return summary, errors


def csv_cell(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def run(output, protocol=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = Path("evaluation/datasets/meddistract-detailed-v1/manifest.json")
    code_paths = [
        "services/error_taxonomy.py",
        "services/benchmark_integrity.py",
        "services/detailed_benchmark.py",
        "services/evaluation.py",
        "services/clinical_metrics.py",
        "services/canonical.py",
    ]
    code_hashes = {name: sha256(name) for name in code_paths}
    manifest_hash = sha256(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    lookup = {c["group_id"]: c for c in manifest["cases"]}
    paths = [
        p
        for folder in (
            "meddistract-detailed-v1",
            "meddistract-detailed-v2",
            "meddistract-recovery-v3",
        )
        for p in (Path("evaluation/runs") / folder).glob("*.json")
    ]
    contract = json.loads(Path(protocol).read_bytes()) if protocol else None
    if contract:
        if (
            contract["manifest_sha256"] != manifest_hash
            or contract["code_sha256"] != code_hashes
            or contract["maximum_normalized_wer"] != 0.05
        ):
            raise ValueError("diagnostic_protocol_changed")
        paths = [Path(row["path"]) for row in contract["source_reports"]]
        if len(paths) != len(set(paths)) or any(
            sha256(row["path"]) != row["sha256"] for row in contract["source_reports"]
        ):
            raise ValueError("diagnostic_source_snapshot_changed")
    reports = []
    csv_path = output / "all-errors.csv"
    columns = [
        "report",
        "candidate",
        "mode",
        "case",
        "condition",
        "failed_case",
        "operation",
        "reference_index",
        "hypothesis_index",
        "reference_token",
        "hypothesis_token",
        "reference_role",
        "uncertain_reference_turn",
        "overlapping_reference_turn",
        "start_ms",
        "end_ms",
        "diagnostic_tags",
    ]
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for path in sorted(paths):
            before = sha256(path)
            report = json.loads(path.read_bytes())
            replay(report, manifest)
            cases = []
            for row in report["cases"]:
                summary, errors = analyze(row, lookup[row["id"]])
                cases.append(summary)
                for error in errors:
                    writer.writerow(
                        {
                            k: csv_cell(v)
                            for k, v in {
                                "report": path.as_posix(),
                                "candidate": report["candidate_id"],
                                "mode": report["mode"],
                                "case": row["id"],
                                "condition": lookup[row["id"]]["condition"],
                                "failed_case": row["failed"],
                                **error,
                            }.items()
                        }
                    )
            if sha256(path) != before:
                raise ValueError("source_report_changed_during_taxonomy")
            reports.append(
                {
                    "path": path.as_posix(),
                    "sha256": before,
                    "complete": report["complete"],
                    "cases": cases,
                }
            )
            print(json.dumps({"report": path.name, "cases": len(cases)}), flush=True)
    if sha256(manifest_path) != manifest_hash or any(
        sha256(name) != expected for name, expected in code_hashes.items()
    ):
        raise ValueError("diagnostic_code_or_manifest_changed_during_execution")
    archive = output / "all-errors.csv.zip"
    info = zipfile.ZipInfo("all-errors.csv", date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(archive, "x") as target:
        with csv_path.open("rb") as source, target.open(info, "w") as destination:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                destination.write(block)
    result = {
        "schema_version": "saved_error_taxonomy_v2",
        "manifest_sha256": manifest_hash,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "code_sha256": code_hashes,
        "config_sha256": content_sha256(
            {
                "tie_policy": "match_substitution_deletion_insertion",
                "max_tokens": 10000,
                "role_insertion_policy": "unattributed",
            }
        ),
        "reports": reports,
        "csv_sha256": sha256(csv_path),
        "csv_archive_sha256": sha256(archive),
        "protocol_sha256": sha256(protocol) if protocol else None,
        "attribution": manifest["attribution"],
        "scoring_profile": "Unchanged primary normalized word edits; raw/normalized CER are additional diagnostics.",
        "tie_policy": "match_then_substitution_then_deletion_then_insertion",
        "maximum_normalized_wer": 0.05,
        "independent_clinical_gold": False,
        "clinical_release": False,
        "limitations": [
            "Reference roles are not predicted diarization; insertions have no inferred speaker owner.",
            "Uncertainty and overlap buckets describe whole reference turns; no words are excluded from primary WER.",
            "Reference gaps do not establish acoustic silence or prove model hallucination.",
            "Saved hypotheses do not measure new inference performance or independent clinical accuracy.",
        ],
    }
    (output / "report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (output / "README.md").write_text(
        "# Saved public-mock error diagnostics\n\n"
        + manifest["attribution"]
        + "\n\nCSV contains every non-match token edit for all saved cases, including failed and partial runs. Case accounting, hashes, role buckets and CER denominators are in report.json. "
        "Extract the complete CSV with `python -m zipfile -e all-errors.csv.zip DESTINATION`; its uncompressed SHA-256 is in report.json. "
        "This is retrospective development analysis, not an independent acceptance cohort or clinical gold. No primary references or WER gates were changed.\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--protocol")
    args = parser.parse_args()
    run(args.out, args.protocol)
