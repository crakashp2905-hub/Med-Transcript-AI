"""One-command local acceptance: no installation, model inference or clinical sign-off."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from services.offline import install
from services.engineering_status import sha256


def source_inventory():
    patterns = (
        "services/**/*.py",
        "tests/**/*.py",
        "apps/clinician-web/src/**/*",
        "apps/clinician-web/e2e/**/*.ts",
        "apps/clinician-web/*.json",
        "apps/clinician-web/*.ts",
        ".github/workflows/*.yml",
        "pyproject.toml",
        "constraints-ci.txt",
        "evaluation/primary-endpoint-registry-v1.json",
        "evaluation/clinical-bindings-development-v1.json",
        "evaluation/contracts/*.json",
        "scripts/*",
        "Dockerfile",
        "compose*.yaml",
    )
    return {
        p.as_posix(): sha256(p)
        for pattern in patterns
        for p in Path(".").glob(pattern)
        if p.is_file() and "__pycache__" not in p.parts
    }


def test_result_summary(result):
    # Do not publish assertion values, source excerpts, parameters or provider text.
    failed = sorted(
        set(re.findall(r"^(?:FAILED|ERROR) ([a-zA-Z0-9_./\\:-]+)", result.stdout, re.M))
    )
    lines = result.stdout.splitlines()
    terminal = lines[-1] if lines else ""
    counts = re.findall(
        r"\b(\d+) (passed|failed|skipped|warnings?|errors?|deselected|xfailed|xpassed)\b",
        terminal,
    )
    summary = (
        ", ".join(f"{count} {kind}" for count, kind in counts)
        or "No recognized pytest summary available"
    )
    duration = re.search(r"\bin (\d+(?:\.\d+)?)s\b", terminal)
    if duration:
        summary += " in " + duration.group(1) + "s"
    return {
        "exit_code": result.returncode,
        "summary": summary,
        "failed_test_ids": failed,
        "raw_failure_text_included": False,
    }


def acceptance(version, run_tests=True, run_build=True):
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", version):
        raise ValueError("Invalid acceptance version")
    output = Path(f"evaluation/reports/offline-acceptance-{version}.json")
    if output.exists():
        raise FileExistsError("Preserve previous acceptance run; use a new version")
    os.environ["MED_TRANSCRIPT_OFFLINE"] = "1"
    install()
    from services.offline_preflight import inspect, check_baseline
    from services.benchmark_integrity import audit
    from services.offline_demo import prepare, walkthrough

    start = time.perf_counter()
    source_hashes = source_inventory()
    results = {}
    preflight = inspect()

    def step(name, fn):
        try:
            value = fn()
            results[name] = {
                "status": "fail"
                if isinstance(value, dict) and value.get("exit_code", 0) != 0
                else "pass",
                "result": value,
            }
        except Exception as exc:
            results[name] = {"status": "fail", "error_type": type(exc).__name__}
        print(
            json.dumps({"check": name, "status": results[name]["status"]}), flush=True
        )

    step(
        "baseline_integrity",
        lambda: check_baseline(
            json.loads(
                Path("evaluation/reports/engineering-baseline.json").read_text(
                    encoding="utf-8"
                )
            )
        ),
    )
    step("saved_metrics_replay", audit)

    # A self-contained model-free application gets isolated storage and credentials.
    def demo():
        if os.getenv("MED_TRANSCRIPT_ENV") == "production":
            raise ValueError("Offline demonstration cannot run in production mode")
        os.environ.update(
            MED_TRANSCRIPT_PROFILE="no_external_dependency",
            MED_TRANSCRIPT_AUTH_MODE="local",
            MED_TRANSCRIPT_DRAFTING_MODE="deterministic",
        )
        app, config = prepare(f"data/offline-acceptance-{uuid4()}")
        return walkthrough(app, config)

    # Run tests before setting the strict demo profile; simulated OIDC tests need
    # their own declared authentication configuration, but never live networking.
    if run_tests:

        def tests():
            env = dict(os.environ)
            env.pop("MED_TRANSCRIPT_PROFILE", None)
            temp = Path("data") / f"pytest-acceptance-{version}-{uuid4()}"
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--basetemp", str(temp)],
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )
            return test_result_summary(result)

        step("backend_tests", tests)
    else:
        results["backend_tests"] = {"status": "not_run", "reason": "explicitly_skipped"}
    if run_build:

        def build():
            if preflight["npm_dependencies"] != "available" or not shutil.which("npm"):
                raise FileNotFoundError("Cached npm dependencies unavailable")
            command = [
                shutil.which("npm"),
                "--prefix",
                "apps/clinician-web",
                "run",
                "build",
            ]
            # npm.cmd requires cmd on Windows; all command arguments are fixed.
            if os.name == "nt":
                command = ["cmd", "/c", *command]
            env = {
                **os.environ,
                "npm_config_offline": "true",
                "npm_config_audit": "false",
                "npm_config_fund": "false",
            }
            result = subprocess.run(
                command, env=env, capture_output=True, text=True, timeout=180
            )
            if result.returncode:
                raise ValueError("Cached frontend build failed")
            return {
                "exit_code": 0,
                "dependency_installation": False,
                "built_index_sha256": sha256("apps/clinician-web/dist/index.html"),
            }

        step("frontend_build", build)
    else:
        results["frontend_build"] = {
            "status": "not_run",
            "reason": "explicitly_skipped",
        }
    step("synthetic_walkthrough", demo)
    # This fixture is exercised through the same independent rule checker used
    # by saved notes; it is a development diagnostic, never clinical gold.
    from services.clinical_evaluation import adversarial

    def clinical_binding_development():
        report = adversarial("evaluation/clinical-bindings-development-v1.json")
        counts = report["confusion_matrix"]
        if (
            counts["false_negative"]
            or counts["false_positive"]
            or counts["true_positive"] != 6
            or counts["true_negative"] != 6
        ):
            raise ValueError("clinical_binding_development_failed")
        return report

    step("clinical_binding_development", clinical_binding_development)
    if source_inventory() != source_hashes:
        results["source_integrity"] = {
            "status": "fail",
            "reason": "source_changed_during_acceptance",
        }
    else:
        results["source_integrity"] = {
            "status": "pass",
            "files_checked": len(source_hashes),
        }
    report = {
        "schema_version": "offline_acceptance_v1",
        "version": version,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_sha256": source_hashes,
        "preflight": preflight,
        "checks": results,
        "wall_seconds": time.perf_counter() - start,
        "release_matrix": {
            "offline_demo": "verified"
            if results["synthetic_walkthrough"]["status"] == "pass"
            else "failed",
            "engineering_verified": "not_established",
            "research_evidence_complete": "not_established",
            "clinical_approved": "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        },
        "maximum_normalized_wer": 0.05,
        "independent_clinical_gold": False,
        "real_patient_release_authorized": False,
        "limitations": [
            "Python sockets are restricted to loopback; this is not an operating-system firewall or native process sandbox.",
            "Skipped checks, missing cached tools and unavailable independent evidence are not passes.",
            "The scripted silent-audio workflow tests software invariants, not speech recognition or clinician performance.",
        ],
    }
    from services.release_policy import validate_matrix, validate_evidence_scope

    validate_matrix(report["release_matrix"])
    validate_evidence_scope(report, "developer_synthetic_oracles")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    Path("data/offline-acceptance-summary.json").write_text(
        json.dumps(
            {
                "report": output.as_posix(),
                "sha256": sha256(output),
                "checks": {k: v["status"] for k, v in results.items()},
                "release_matrix": report["release_matrix"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Offline acceptance summary",
        "",
        "Clinical release: `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED`.",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for key, value in sorted(
        results.items(), key=lambda item: item[1]["status"] == "pass"
    ):
        lines.append(f"| {key} | {value['status']} |")
    lines += [
        "",
        f"Report: [{output.name}](../{output.as_posix()})",
        "",
        *report["limitations"],
    ]
    Path("docs/offline-acceptance-summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    result = acceptance(args.version, not args.skip_tests, not args.skip_build)
    if any(c["status"] != "pass" for c in result["checks"].values()):
        raise SystemExit(1)
