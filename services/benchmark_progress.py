"""Publish local benchmark progress from complete reports and per-clip logs only."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from services.benchmark_ranking import rank


def snapshot(root="."):
    root = Path(root)
    suite = json.loads((root / "evaluation/expanded-suite-v1.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / suite["manifest"]).read_text(encoding="utf-8"))
    expected = {s["sample_id"] for s in manifest["samples"]}
    rows = []
    for job in suite["jobs"]:
        cid = job["candidate_id"]
        relative = Path("data/datasets/primock57-expanded-v1/results") / f"{cid}.json"
        report, log = root / relative, root / relative.with_suffix(".log")
        row = {"candidate_id": cid, "status": "queued", "processed": 0,
            "total": len(expected), "normalized_wer": None, "failed_samples": None}
        if log.exists():
            seen = set()
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    item = json.loads(line)
                    if item.get("sample_id") in expected:
                        seen.add(item["sample_id"])
                except (ValueError, AttributeError):
                    pass
            row.update(status="running", processed=len(seen))
        if report.exists():
            result = rank(root / suite["manifest"], root / suite["lock"],
                [{"candidate_id": cid, "status": "completed", "report": str(relative)}], root)
            if result["ranked"]:
                measured = result["ranked"][0]
                row.update(status="completed", processed=len(expected), normalized_wer=measured["normalized_wer"],
                    failed_samples=measured["failed_samples"], gate=measured["wer_gate"]["status"])
        rows.append(row)
    return {"updated_at": datetime.now(timezone.utc).isoformat(), "maximum_normalized_wer": suite["maximum_normalized_wer"],
        "sample_count": len(expected), "consultation_groups": len({s["group_id"] for s in manifest["samples"]}),
        "complete": all(r["status"] == "completed" for r in rows), "models": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    output = Path("evaluation/expanded-progress.json")
    while True:
        result = snapshot()
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        temporary.replace(output)
        if not args.watch or result["complete"]:
            break
        time.sleep(10)


if __name__ == "__main__":
    main()
