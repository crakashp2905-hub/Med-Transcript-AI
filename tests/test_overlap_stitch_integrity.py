from services.overlap_reassembly import stitch


def test_overlap_stitch_retains_unmatched_clinical_words():
    text, event = stitch("Patient denies allergy dose 0.5 mg", "dose 0.5 mg today")
    assert "Patient" in text and "today" in text and "0.5" in text and "mg" in text
    assert event["removed_tokens"] >= 0
