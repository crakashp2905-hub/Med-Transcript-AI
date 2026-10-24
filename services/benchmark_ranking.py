"""Rank only complete comparable runs against a frozen reference dataset."""

import argparse
import hashlib
import html
import json
import os
from fractions import Fraction
from pathlib import Path

from services.evaluation import score, tokens, wer_gate


SCORING = "lowercase_words_preserve_decimals_units_negation_v1"


def rank(manifest_path, lock_path, entries, root):
    body = Path(manifest_path).read_bytes()
    manifest, lock = json.loads(body), json.loads(Path(lock_path).read_text())
    digest = hashlib.sha256(body).hexdigest()
    if digest != lock["manifest_sha256"] or manifest["dataset_id"] != lock["dataset_id"]:
        raise ValueError("Frozen dataset integrity failure")
    if lock["maximum_normalized_wer"] != .03:
        raise ValueError("Project ranking requires the fixed 3% WER limit")
    truth = {s["sample_id"]: s for s in manifest["samples"]}
    if len(truth) != len(manifest["samples"]):
        raise ValueError("Duplicate reference sample")
    measured, unranked, seen = [], [], set()
    for entry in entries:
        cid = entry["candidate_id"]
        if cid in seen:
            raise ValueError("Duplicate candidate entry")
        seen.add(cid)
        if entry["status"] != "completed":
            unranked.append(dict(entry))
            continue
        try:
            report_path = (Path(root) / entry["report"]).resolve()
            report_body = report_path.read_bytes()
            report = json.loads(report_body)
            if (report.get("manifest_sha256") != digest or report.get("dataset_id") != manifest["dataset_id"]
                    or report.get("scoring_profile") != SCORING
                    or report.get("failure_policy") != lock["failure_policy"]):
                raise ValueError("incomparable_dataset_or_scoring")
            rows = report["samples"]
            if len(rows) != len(truth) or {r["sample_id"] for r in rows} != set(truth):
                raise ValueError("incomplete_or_duplicate_sample_coverage")
            failures, words, edits = 0, 0, 0
            for row in rows:
                reference = truth[row["sample_id"]]
                expected = len(tokens(reference["reference"]))
                if row["group_id"] != reference["group_id"] or row["reference_words"] != expected:
                    raise ValueError("reference_counts_or_groups_changed")
                value = row["normalized_edits"]
                if type(value) is not int or value < 0:
                    raise ValueError("invalid_edit_count")
                if row["status"] == "failed":
                    failures += 1
                    if value != expected:
                        raise ValueError("failed_sample_denominator_changed")
                elif row["status"] != "completed":
                    raise ValueError("unfinished_sample")
                if "hypothesis" in row and value != score(reference["reference"], row["hypothesis"])["normalized_edits"]:
                    raise ValueError("hypothesis_score_mismatch")
                words += expected
                edits += value
            if (words, edits, failures, len(rows)) != (report["reference_words"], report["normalized_edits"], report["failed_samples"], report["sample_count"]):
                raise ValueError("aggregate_counts_do_not_match_samples")
            if not words or failures == len(rows):
                raise ValueError("no_valid_scored_outputs")
            metric = edits / words
            if report["normalized_wer"] != metric:
                raise ValueError("reported_wer_does_not_match_counts")
            measured.append({"candidate_id": cid, "status": "completed", "normalized_wer": metric,
                "runtime_variant": entry.get("runtime_variant", report["profile_id"]),
                "normalized_edits": edits, "reference_words": words, "failed_samples": failures,
                "sample_count": len(rows), "profile_sha256": report["profile_sha256"],
                "model_revision": report["model_revision"], "report": entry["report"],
                "report_sha256": hashlib.sha256(report_body).hexdigest(),
                "wer_gate": wer_gate(report, lock["maximum_normalized_wer"]),
                "elapsed_seconds": round(sum(r["elapsed_seconds"] for r in rows), 4)})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            unranked.append({**entry, "status": "invalid_report", "reason": str(exc)})
    measured.sort(key=lambda r: (Fraction(r["normalized_edits"], r["reference_words"]), r["candidate_id"]))
    previous, place = None, 0
    for index, row in enumerate(measured, 1):
        ratio = Fraction(row["normalized_edits"], row["reference_words"])
        if ratio != previous:
            place = index
        row["rank"] = place
        previous = ratio
    return {"schema_version": "1.0", "dataset_id": manifest["dataset_id"], "manifest_sha256": digest,
        "scope": lock["allowed_use"], "ranking_rule": "ascending_unrounded_aggregate_normalized_wer_shared_ranks_for_ties",
        "maximum_normalized_wer": lock["maximum_normalized_wer"], "ranked": measured, "unranked": unranked,
        "production_model_selected": None, "clinical_release_gate": "not_evaluated",
        "limitations": lock.get("limitations", "Six clips from one consultation; upstream references are not independently clinically adjudicated. No production winner from this screening set.")}


def render(result):
    lines = ["# ASR benchmark ranking", "", f"Dataset: `{result['dataset_id']}`", "",
        f"Manifest SHA-256: `{result['manifest_sha256']}`", "",
        "Required normalized WER: **≤3%**. Lower is better. Equal exact scores share a rank.", "",
        "| Rank | Model/configuration | Normalized WER | Failed clips | 3% gate |",
        "| --- | --- | ---: | ---: | --- |"]
    for row in result["ranked"]:
        lines.append(f"| {row['rank']} | {row['candidate_id']} | {row['normalized_wer']:.2%} | {row['failed_samples']} | {row['wer_gate']['status']} |")
    lines += ["", "## Unranked candidates", "", "| Candidate | Status | Reason |", "| --- | --- | --- |"]
    for row in result["unranked"]:
        reason = row.get("reason", "No complete comparable run").replace("|", "/").replace("\n", " ")
        lines.append(f"| {row['candidate_id']} | {row['status']} | {reason} |")
    lines += ["", result["limitations"], "", "Paid calls are disabled. Blocked and untested models have no quality rank. Failed clips remain in measured runs' denominators. No production model is selected.", ""]
    return "\n".join(lines)


def render_html(result, manifest, dataset_path="datasets/primock57-smoke-v1"):
    esc = lambda value: html.escape(str(value), quote=True)
    measured = ''.join(f'<tr><td>{r["rank"]}</td><th>{esc(r["candidate_id"])}<br><small>{esc(r["runtime_variant"])}</small></th><td>{r["normalized_wer"]:.2%}</td><td>{r["normalized_edits"]}/{r["reference_words"]}</td><td>{r["failed_samples"]}</td><td>{esc(r["wer_gate"]["status"]).upper()}</td></tr>' for r in result['ranked'])
    blocked = ''.join(f'<tr><th>{esc(r["candidate_id"])}</th><td>{esc(r["status"])}</td><td>{esc(r.get("reason", "No complete comparable run"))}</td></tr>' for r in result['unranked'])
    recordings = ''.join(f'<article><h3>{esc(s["sample_id"])}</h3><audio controls preload="none" src="{esc(dataset_path)}/{esc(s["audio"])}"></audio><p>{esc(s["reference"])}</p></article>' for s in manifest['samples'])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ASR model comparison</title>
<style>body{{font:16px/1.6 system-ui;margin:0;background:#f1f6f5;color:#173c39}}main{{max-width:1180px;margin:auto;padding:40px 24px}}h1{{font-size:36px;line-height:1.2}}.eyebrow{{font-size:13px;letter-spacing:.1em;font-weight:700}}.notice,article,.table{{background:white;border:1px solid #d5e2df;border-radius:12px;padding:20px;margin:20px 0}}.table{{overflow-x:auto;padding:0}}table{{width:100%;border-collapse:collapse;text-align:left}}td,th{{padding:14px;border-bottom:1px solid #e1ebe8;vertical-align:top}}thead{{background:#dcebe7}}code{{overflow-wrap:anywhere;font-size:12px}}audio{{max-width:100%}}small{{color:#42635f}}article h3{{overflow-wrap:anywhere}}@media(max-width:600px){{main{{padding:24px 14px}}h1{{font-size:28px}}td,th{{padding:10px}}}}</style>
<main><p class="eyebrow">MED TRANSCRIPT · REPRODUCIBLE SCREENING</p><h1>ASR models, ranked by measured word error rate</h1>
<div class="notice"><strong>Required normalized WER: ≤3.00%</strong><p>Lower is better. Ties share an exact rank. This is a development evaluation dataset, not a clinical acceptance result. No production model has been selected.</p></div>
<h2>Measured models</h2><div class="table"><table><thead><tr><th>Rank</th><th>Model / runtime variant</th><th>Normalized WER</th><th>Edits / words</th><th>Failed clips</th><th>3% gate</th></tr></thead><tbody>{measured}</tbody></table></div>
<h2>Unranked candidates</h2><p>Access, runtime and resource blockers do not establish a model's accuracy. Paid calls are disabled.</p><div class="table"><table><thead><tr><th>Candidate</th><th>Status</th><th>Reason</th></tr></thead><tbody>{blocked}</tbody></table></div>
<h2>Frozen reference dataset</h2><p>{esc(result['dataset_id'])}</p><p><small>Manifest SHA-256</small><br><code>{esc(result['manifest_sha256'])}</code></p><p>{esc(result['limitations'])}</p>
<details><summary>Listen to the {len(manifest['samples'])} recordings and read their reference transcripts</summary>{recordings}</details>
<p><small>Source: PriMock57, Babylon Health; Papadopoulos Korfiatis, Moramarco, Sarac and Savkov (2022), CC BY 4.0. Normalized and cropped from simulated consultation recordings. See the dataset directory for license and attribution.</small></p></main></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="evaluation/datasets/primock57-smoke-v1/manifest.json")
    parser.add_argument("--lock", default="evaluation/datasets/primock57-smoke-v1/lock.json")
    parser.add_argument("--ledger", default="evaluation/benchmark-ledger.json")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="evaluation/leaderboard.json")
    args = parser.parse_args()
    result = rank(args.manifest, args.lock, json.loads(Path(args.ledger).read_text())["candidates"], args.root)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(render(result), encoding="utf-8")
    # Standalone file is intentionally self-contained and can be opened directly.
    dataset_path = Path(os.path.relpath(Path(args.manifest).resolve().parent, path.resolve().parent)).as_posix()
    path.with_suffix(".html").write_text(render_html(result, json.loads(Path(args.manifest).read_text()), dataset_path), encoding="utf-8")
    print(json.dumps({"ranked": len(result["ranked"]), "unranked": len(result["unranked"]), "out": str(path)}))


if __name__ == "__main__":
    main()
