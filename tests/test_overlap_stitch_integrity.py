from services.overlap_reassembly import stitch


def test_overlap_stitch_retains_unmatched_clinical_words():
    text, event = stitch("Patient denies allergy dose 0.5 mg", "dose 0.5 mg today")
    assert "Patient" in text and "today" in text and "0.5" in text and "mg" in text
    assert event["removed_tokens"] >= 0


def test_sequence_alignment_handles_shared_prefix_and_backtracking():
    shared, shared_event = stitch("the dose is 500 mg", "dose is 500 mg daily")
    backtracked, backtrack_event = stitch(
        "daily dose is 500 mg", "500 mg daily frequency"
    )
    assert shared == "the dose is 500 mg daily"
    assert shared_event["removed_tokens"] == 4
    assert backtracked.endswith("daily frequency")
    assert backtrack_event["removed_tokens"] == 2


def test_sequence_alignment_preserves_repeated_medical_term_mentions():
    text, event = stitch(
        "metformin dose is 500 mg metformin",
        "500 mg metformin twice daily",
    )
    assert text == "metformin dose is 500 mg metformin twice daily"
    assert event["removed_tokens"] == 3
    assert event["method"] == "exact"
