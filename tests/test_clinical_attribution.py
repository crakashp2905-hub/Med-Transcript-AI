from services.clinical_attribution import classify


def test_attribution_distinguishes_family_speculation_questions_and_plans():
    assert classify("Mother has diabetes.")["subject"] == "family"
    assert classify("Maybe the patient has asthma.")["assertion"] == "uncertain"
    assert classify("Do you have chest pain?")["assertion"] == "uncertain"
    assert classify("")["assertion"] == "not_stated"
    assert classify("Allergy not documented.")["assertion"] == "not_stated"
    assert classify("Not sure about an allergy.")["assertion"] == "uncertain"
    assert classify("No chest pain.")["assertion"] == "negated"
    result = classify("Plan to start treatment.")
    assert (
        result["action_status"] == "planned" and result["diagnosis_inferred"] is False
    )
