from services.evaluation import tokens, distance, score


def test_scoring_preserves_clinically_material_tokens():
    assert tokens("No fever. Dose 0.5 mg.") == ["no", "fever", "dose", "0.5", "mg"]
    assert score("No fever. Dose 0.5 mg.", "Fever. Dose 5 mcg.")["normalized_edits"] == 3


def test_failed_sample_empty_hypothesis_counts_all_reference_deletions():
    metrics = score("Patient denies drug allergies", "")
    assert metrics["reference_words"] == metrics["normalized_edits"] == 4
    assert distance([], ["hallucinated", "speech"]) == 2
