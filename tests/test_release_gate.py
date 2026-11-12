from services.release_gate import check


def test_release_gate_blocks_any_migration_evidence_schema_stale_or_critical_failure():
    state = {
        key: True
        for key in (
            "migration_ok",
            "evidence_ok",
            "schemas_supported",
            "stale_approvals_absent",
            "critical_verification_complete",
        )
    }
    assert check(state)["status"] == "pass"
    state["evidence_ok"] = False
    result = check(state)
    assert result["status"] == "blocked" and "evidence_ok" in result["missing"]
    assert result["real_patient_release_authorized"] is False
