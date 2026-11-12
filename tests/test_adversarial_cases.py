from services.asr.adversarial_cases import manifest


def test_adversarial_manifest_covers_required_synthetic_cases():
    result = manifest()
    assert {row["id"] for row in result["cases"]} == {
        "silence",
        "clipping",
        "repeated_prompt",
        "numerical_dose",
        "medical_homophone",
        "ambiguous_utterance",
    }
    assert all(
        row["synthetic"] and row["clinical_gold"] is False for row in result["cases"]
    )
    assert result["real_patient_release_authorized"] is False
