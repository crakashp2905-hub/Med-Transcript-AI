"""Publish only complete local model runs, retaining all blocked candidates and failures."""

import argparse
import json
from pathlib import Path

from services.benchmark_ranking import rank, render, render_html
from services.expanded_summary import summarize, markdown


def publish(root="."):
    root = Path(root)
    suite = json.loads((root / "evaluation/expanded-suite-v1.json").read_text(encoding="utf-8"))
    original = json.loads((root / "evaluation/benchmark-ledger.json").read_text(encoding="utf-8"))
    jobs = {j["candidate_id"]: j for j in suite["jobs"]}
    if len(jobs) != 7:
        raise ValueError("Exactly seven local configurations are required")
    sources = []
    for cid, job in jobs.items():
        sources.append({"candidate_id": cid, "status": "completed",
            "report": f"data/datasets/primock57-expanded-v1/results/{cid}.json",
            "runtime_variant": job["runtime_variant"]})
    checked = rank(root / suite["manifest"], root / suite["lock"], sources, root)
    if len(checked["ranked"]) != 7 or checked["unranked"]:
        raise ValueError("All seven complete valid local runs are required before publication")
    destination = root / "evaluation/runs/primock57-expanded-v1"
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    for entry in original["candidates"]:
        cid = entry["candidate_id"]
        if cid in jobs:
            source = root / f"data/datasets/primock57-expanded-v1/results/{cid}.json"
            (destination / f"{cid}.json").write_bytes(source.read_bytes())
            entry = {"candidate_id": cid, "status": "completed", "report": f"evaluation/runs/primock57-expanded-v1/{cid}.json",
                "runtime_variant": jobs[cid]["runtime_variant"]}
            if cid == "omi-med-stt-v1":
                entry["runtime_variant"] += "; persistent C API with explicit Windows DLL cleanup"
        entries.append(entry)
    ledger = {"schema_version": "1.0", "dataset": suite["manifest"],
        "protocol": "evaluation/expanded-protocol-v1.json", "maximum_normalized_wer": .05,
        "policy": "Local/public models first; no paid calls or gated access approvals. All seven local runs use text-only adapters.",
        "runtime_repair_audit": "evaluation/reports/expanded-omi-runtime-repair-2026-10-24.md", "candidates": entries}
    (root / "evaluation/expanded-ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    # Includes configuration hashes, public source profiles, artifacts and versions.
    summary = summarize(root)
    result = rank(root / suite["manifest"], root / suite["lock"], entries, root)
    path = root / "evaluation/expanded-leaderboard.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(render(result), encoding="utf-8")
    manifest = json.loads((root / suite["manifest"]).read_text(encoding="utf-8"))
    path.with_suffix(".html").write_text(render_html(result, manifest, "datasets/primock57-expanded-v1"), encoding="utf-8")
    path = root / "evaluation/reports/expanded-comparison-2026-10-24.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(markdown(summary), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = publish(args.root)
    print(json.dumps({"ranked": len(result["ranked"]), "unranked": len(result["unranked"]),
        "models": [{"id": r["candidate_id"], "normalized_wer": r["normalized_wer"], "failures": r["failed_samples"],
            "gate": r["wer_gate"]["status"]} for r in result["ranked"]]}))


if __name__ == "__main__":
    main()
