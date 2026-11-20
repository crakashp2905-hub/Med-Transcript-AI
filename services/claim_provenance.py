"""Build a hash-linked index for explicit 10/10 engineering claims."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


CLAIM_SPECS = [
    {
        "id": "overall-self-contained-engineering-target",
        "label": "10/10 self-contained engineering and research prototype",
        "anchors": [
            (
                "docs/plans/zero-external-checklist.md",
                "A **10/10 self-contained engineering and research prototype** means:",
            )
        ],
        "evidence": [
            "MTA-17-01",
            "MTA-14-09",
            "MTA-16-13",
            "MTA-17-02",
            "MTA-17-03",
            "MTA-17-07",
            "MTA-17-09",
        ],
        "status": "not_awarded_target_only",
        "assessment": "The checklist defines a target, not a current score. Representative evidence is linked by dimension; unresolved P0 risks and external/clinical gates prevent an overall 10/10 award.",
    },
    {
        "id": "architecture-maintainability",
        "label": "Architecture/maintainability: typed services, compatibility, manageable modules",
        "anchors": [
            (
                "docs/plans/zero-external-checklist.md",
                "Architecture/maintainability | 15",
            )
        ],
        "evidence": ["MTA-17-01"],
        "status": "supporting_evidence_only_not_scored",
        "assessment": "Architecture contracts and module references are checked; this is not a comprehensive maintainability score.",
    },
    {
        "id": "reliability-recovery",
        "label": "Reliability and recovery: synthetic crash/retry/revocation paths tested",
        "anchors": [
            ("docs/plans/zero-external-checklist.md", "Reliability and recovery | 15")
        ],
        "evidence": ["MTA-14-09", "MTA-17-07"],
        "status": "supporting_evidence_only_not_scored",
        "assessment": "Synthetic recovery targets and the offline demo have focused evidence; the full crash/retry/revocation matrix is not certified complete by these checks.",
    },
    {
        "id": "safety-by-design",
        "label": "Safety by design: predefined synthetic invariant violations and fail-closed approval",
        "anchors": [("docs/plans/zero-external-checklist.md", "Safety by design | 20")],
        "evidence": ["MTA-17-07"],
        "status": "not_met_open_p0_and_clinical_evidence",
        "assessment": "A synthetic dose error is blocked in the offline workflow, but risk register P0 items and independent clinical misses remain unresolved.",
    },
    {
        "id": "research-evaluation-integrity",
        "label": "Research/evaluation integrity: exact reproducibility, fair baselines and full failures",
        "anchors": [
            (
                "docs/plans/zero-external-checklist.md",
                "Research/evaluation integrity | 20",
            )
        ],
        "evidence": ["MTA-17-02", "MTA-17-03"],
        "status": "supporting_evidence_only_not_scored",
        "assessment": "Reproducibility and publication bundles preserve negative results; some assets/licenses and independent clinical evidence remain unavailable.",
    },
    {
        "id": "security-privacy-simulations",
        "label": "Security and privacy simulations: offline auth, isolation, tamper/backup tests",
        "anchors": [
            (
                "docs/plans/zero-external-checklist.md",
                "Security and privacy simulations | 15",
            )
        ],
        "evidence": ["MTA-16-13", "MTA-14-09"],
        "status": "supporting_evidence_only_not_scored",
        "assessment": "Local onboarding and synthetic backup checks are evidenced; deployment-owner security review and key custody are not established.",
    },
    {
        "id": "ux-reproducibility",
        "label": "UX and reproducibility: one-command offline workflow and inspector",
        "anchors": [
            ("docs/plans/zero-external-checklist.md", "UX and reproducibility | 10")
        ],
        "evidence": ["MTA-17-07", "MTA-17-08"],
        "status": "supporting_evidence_only_not_scored",
        "assessment": "A model-free demo and static synthetic showcase are checked; this does not establish usability with clinicians.",
    },
    {
        "id": "documentation-product-clarity",
        "label": "Documentation and product clarity: accurate claims, report links, limits and licenses",
        "anchors": [
            (
                "docs/plans/zero-external-checklist.md",
                "Documentation and product clarity | 5",
            )
        ],
        "evidence": ["MTA-17-09", "MTA-17-02"],
        "status": "supporting_evidence_only_not_scored",
        "assessment": "Planning artifacts and reproducibility limitations are documented; this does not award the rubric points.",
    },
    {
        "id": "engineering-100-point-total",
        "label": "100/100 engineering-prototype points",
        "anchors": [
            (
                "docs/plans/zero-external-checklist.md",
                "**Total** | **100** | **100/100 engineering-prototype points is a target, not a guaranteed outcome**",
            )
        ],
        "evidence": [
            "MTA-17-01",
            "MTA-14-09",
            "MTA-16-13",
            "MTA-17-02",
            "MTA-17-03",
            "MTA-17-07",
            "MTA-17-09",
        ],
        "status": "target_not_scored",
        "assessment": "No 100/100 score has been calculated or claimed.",
    },
    {
        "id": "clinical-10of10-explicit-nonclaim",
        "label": "Clinical accuracy / clinical deployment readiness 10/10",
        "anchors": [
            (
                "docs/plans/zero-external-checklist.md",
                "It **does not** mean 10/10 clinical accuracy",
            ),
            (
                "docs/plans/zero-external-checklist.md",
                "clinical deployment readiness into 10/10",
            ),
        ],
        "evidence": ["MTA-17-03", "MTA-16-16"],
        "status": "explicitly_not_claimed",
        "assessment": "The checklist explicitly excludes clinical scoring. Benchmark candidates fail the 5% WER gate and independent reviewers are unavailable.",
    },
    {
        "id": "synthetic-restore-count",
        "label": "10/10 baseline synthetic encounters restored in the recovery test",
        "anchors": [
            (
                "evaluation/reports/master-task-mta-14-09-4e5a5b9.json",
                "restored 10/10 baseline synthetic encounters",
            )
        ],
        "evidence": ["MTA-14-09"],
        "status": "verified_narrow_synthetic_result",
        "assessment": "This is a narrowly scoped test observation, not a 10/10 product, reliability or clinical score.",
    },
]

TEST_IDS = {
    (
        "MTA-14-09",
        "synthetic_restore_and_recovery_targets",
    ): "tests/test_maintenance.py::test_local_restore_recovery_target_and_snapshot_rpo",
    (
        "MTA-14-09",
        "operations_playbook_contract",
    ): "tests/test_operations_playbook.py::test_operations_playbook_contains_migration_incident_and_stop_procedures",
    (
        "MTA-16-13",
        "onboarding_offline",
    ): "tests/test_offline_onboarding.py::test_local_onboarding_needs_no_email_or_oauth_activation",
    (
        "MTA-16-16",
        "blank_results_and_gate_test",
    ): "tests/test_human_study_protocol_skeleton.py::test_future_human_study_protocol_has_no_fabricated_results_or_approval",
    (
        "MTA-17-01",
        "architecture_contracts",
    ): "tests/test_architecture_spec.py::test_architecture_spec_references_existing_modules_and_typed_contracts",
    (
        "MTA-17-02",
        "repro_pack_v3",
    ): "tests/test_repro_bundle.py::test_repro_bundle_has_hashes_commands_and_negative_results",
    (
        "MTA-17-03",
        "publication_bundle",
    ): "tests/test_publication_bundle.py::test_publication_tables_retain_gate_failures_unranked_candidates_and_limits",
    (
        "MTA-17-07",
        "one_command_demo_workflow",
    ): "tests/test_offline_engineering.py::test_offline_scripted_workflow_blocks_dose_error_and_viewer_write",
    (
        "MTA-17-08",
        "investor_synthetic_readonly_showcase",
    ): "tests/test_investor_demo_static.py::test_investor_preview_uses_synthetic_source_fixture_without_api_calls",
    (
        "MTA-17-09",
        "product_management_artifacts_and_evidence_boundaries",
    ): "tests/test_product_management_bundle.py::test_product_management_artifacts_are_present_and_cross_linked",
}


def _sha256(path):
    if path.suffix.lower() == ".md" and "evaluation" not in path.parts:
        content = path.read_text(encoding="utf-8").encode("utf-8")
    else:
        content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def _anchor(root, relative, text):
    path = root / relative
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines, 1) if text in line]
    if len(hits) != 1:
        raise ValueError(f"claim_anchor_not_unique:{relative}:{text}")
    return {"path": relative, "line": hits[0], "text": text, "sha256": _sha256(path)}


def build(root=".", source_commit=None):
    root = Path(root).resolve()
    ledger_path = root / "evaluation/master-task-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    tasks = {task["id"]: task for task in ledger["tasks"]}
    if source_commit is None:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()

    claims = []
    for spec in CLAIM_SPECS:
        anchors = [_anchor(root, *anchor) for anchor in spec["anchors"]]
        evidence = []
        for task_id in spec["evidence"]:
            task = tasks[task_id]
            if task["status"] not in {"verified", "implemented"}:
                raise ValueError(f"claim_task_without_reviewed_status:{task_id}")
            for result in task.get("test_results", []):
                if result["status"] != "pass":
                    continue
                report = root / result["report"]
                if _sha256(report) != result["report_sha256"]:
                    raise ValueError(f"claim_report_hash_mismatch:{task_id}")
                test_id = TEST_IDS.get(
                    (task_id, result["check"]), result.get("test_id", result["check"])
                )
                test_path, _, test_name = test_id.partition("::")
                if not (root / test_path).is_file() or not test_name:
                    raise ValueError(f"claim_test_id_missing:{task_id}:{test_id}")
                if f"def {test_name.split('[')[0]}(" not in (
                    root / test_path
                ).read_text(encoding="utf-8"):
                    raise ValueError(f"claim_test_function_missing:{task_id}:{test_id}")
                evidence.append(
                    {
                        "task_id": task_id,
                        "task_status": task["status"],
                        "test_id": test_id,
                        "report_check": result["check"],
                        "source_commit": task["source_commit"],
                        "artifact_path": result["report"],
                        "artifact_sha256": result["report_sha256"],
                    }
                )
        if not evidence:
            raise ValueError(f"claim_without_test_evidence:{spec['id']}")
        claims.append(
            {
                "claim_id": spec["id"],
                "label": spec["label"],
                "status": spec["status"],
                "assessment": spec["assessment"],
                "source_anchors": anchors,
                "evidence": evidence,
            }
        )
    return {
        "schema_version": "claim_provenance_v1",
        "source_commit": source_commit,
        "source_scope": [
            "docs/plans/zero-external-checklist.md explicit engineering rubric and clinical scope boundary",
            "evaluation/reports/master-task-mta-14-09-4e5a5b9.json narrow synthetic recovery observation",
        ],
        "claims": claims,
        "limitations": [
            "Evidence links are traceability, not a score or proof that an entire rubric dimension is satisfied.",
            "The overall 10/10 and 100/100 targets are not awarded.",
            "No clinical accuracy, safety certification, customer validation or clinical deployment claim is made.",
        ],
    }


def render_markdown(value):
    lines = [
        "# 10/10 claim provenance ledger",
        "",
        f"**Generated for source commit:** `{value['source_commit']}`  ",
        "**Interpretation:** evidence links support traceability; they do not award points or establish clinical validity.",
        "",
        "| Claim | State | Source anchor | Test ID | Evidence commit | Output artifact | SHA-256 |",
        "|---|---|---|---|---|---|---|",
    ]
    for claim in value["claims"]:
        for evidence in claim["evidence"]:
            anchor = claim["source_anchors"][0]
            lines.append(
                f"| {claim['label']} | {claim['status']} | `{anchor['path']}:{anchor['line']}` | "
                f"`{evidence['test_id']}` | `{evidence['source_commit']}` | "
                f"`{evidence['artifact_path']}` | `{evidence['artifact_sha256']}` |"
            )
    lines += ["", "## Assessment limits", ""]
    lines.extend(f"- {item}" for item in value["limitations"])
    lines += [
        "",
        "The only verified claim containing `10/10` as a measured result is the narrow synthetic restore count. It is not a product score.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    value = build(root, args.source_commit)
    json_path = root / "evaluation/claim-provenance/10of10-provenance-v2.json"
    md_path = root / "docs/research/claim-provenance-10of10-v2.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    md_path.write_text(render_markdown(value), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "claims": len(value["claims"]),
            }
        )
    )


if __name__ == "__main__":
    main()
