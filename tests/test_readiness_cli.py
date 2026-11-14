from services.status_report import readiness_checks


def test_missing_readiness_inputs_are_never_reported_as_pass_or_silently_omitted():
    checks = readiness_checks(
        offline_mode=False,
        acceptance_present=False,
        current_demo_pass=False,
        engineering_evidence_valid=False,
        production_model_selected=False,
    )
    assert checks["overall"]["status"] == "BLOCKED"
    assert checks["latest_acceptance"]["status"] == "UNKNOWN"
    assert checks["engineering_evidence"]["status"] == "BLOCKED"
    assert checks["asr_model_admission"]["status"] == "BLOCKED"
    assert checks["clinical_validation"]["status"] == "BLOCKED"
    assert checks["physical_audio_hardware"]["status"] == "UNKNOWN"
    assert checks["ehr_receiver_validation"]["status"] == "UNKNOWN"
    assert all(
        value["status"] in {"PASS", "BLOCKED", "UNKNOWN"} for value in checks.values()
    )
    assert all(value["reason"] for value in checks.values())


def test_even_all_local_checks_do_not_clear_external_clinical_gate():
    checks = readiness_checks(
        offline_mode=True,
        acceptance_present=True,
        current_demo_pass=True,
        engineering_evidence_valid=True,
        production_model_selected=False,
    )
    assert checks["offline_mode"]["status"] == "PASS"
    assert checks["latest_acceptance"]["status"] == "PASS"
    assert checks["engineering_evidence"]["status"] == "PASS"
    assert checks["clinical_validation"]["status"] == "BLOCKED"
    assert checks["overall"]["status"] == "BLOCKED"
