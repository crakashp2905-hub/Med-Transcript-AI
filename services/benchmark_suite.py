"""Execute predeclared local-only benchmarks in isolated processes; never provision models."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.profiles import load_profiles
from services.benchmark_ranking import rank


def execute(suite_path, lane):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    destination = Path("data/datasets/primock57-expanded-v1/results")
    destination.mkdir(parents=True, exist_ok=True)
    errors = []
    for job in suite["jobs"]:
        if job["lane"] != lane:
            continue
        cid = job["candidate_id"]
        output = destination / f"{cid}.json"
        entry = {"candidate_id": cid, "status": "completed", "report": str(output)}
        if output.exists():
            checked = rank(suite["manifest"], suite["lock"], [entry], ".")
            if not checked["unranked"]:
                print(json.dumps({"candidate_id": cid, "status": "complete_report_reused"}), flush=True)
                continue
            raise ValueError(f"Existing invalid report must be reviewed: {cid}")
        args = [sys.executable, "-m", "services.benchmark_text", "--manifest", suite["manifest"],
            "--runtime", job["runtime"], "--out", str(output),
            "--max-normalized-wer", str(suite["maximum_normalized_wer"])]
        if job["runtime"] == "whisper":
            profiles = str(Path("data") / job["profile_file"])
            profile = load_profiles(profiles)[job["profile_id"]]
            if profile.sha256 != job["source_profile_sha256"]:
                raise ValueError(f"Predeclared profile changed: {cid}")
            args += ["--profiles", profiles, "--profile-id", job["profile_id"]]
        else:
            artifacts = {p.name: file_sha256(p) for p in Path(job["model_dir"]).iterdir() if p.is_file()}
            if artifacts != job["expected_artifacts"]:
                raise ValueError(f"Predeclared artifacts changed: {cid}")
            for key in ("model_dir", "revision", "package_dir"):
                args += ["--" + key.replace("_", "-"), job[key]]
        print(json.dumps({"candidate_id": cid, "status": "running", "output": str(output)}), flush=True)
        with output.with_suffix(".log").open("w", encoding="utf-8") as log:
            result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=False)
        checked = rank(suite["manifest"], suite["lock"], [entry], ".")
        if result.returncode not in (0, 2) or checked["unranked"]:
            errors.append(cid)
            print(json.dumps({"candidate_id": cid, "status": "runtime_failed", "exit_code": result.returncode}), flush=True)
        else:
            row = checked["ranked"][0]
            print(json.dumps({"candidate_id": cid, "status": "completed", "normalized_wer": row["normalized_wer"],
                "failed_samples": row["failed_samples"], "gate": row["wer_gate"]}), flush=True)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="evaluation/expanded-suite-v1.json")
    parser.add_argument("--lane", choices=["a", "b"], required=True)
    args = parser.parse_args()
    raise SystemExit(1 if execute(args.suite, args.lane) else 0)


if __name__ == "__main__":
    main()
