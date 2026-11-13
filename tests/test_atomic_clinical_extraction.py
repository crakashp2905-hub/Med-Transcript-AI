from uuid import uuid4

from services.review.clinical import atomic_spans, extract


def transcript(text):
    return {"segments": [{"segment_id": str(uuid4()), "text": text}]}


def test_but_contrast_splits_explicit_negated_and_affirmed_symptoms():
    facts = extract(transcript("No cough but fever."))

    assert [fact["text"] for fact in facts] == ["No cough", "fever."]
    assert [fact["assertion"] for fact in facts] == ["negated", "affirmed"]
    for fact in facts:
        assert fact["evidence"]["quote"] == fact["text"]
        assert fact["evidence"]["end_char"] - fact["evidence"]["start_char"] == len(
            fact["text"]
        )


def test_compound_medications_keep_each_dose_and_frequency_with_its_drug():
    facts = extract(
        transcript("Takes metformin 500 mg daily and warfarin 5 mg twice daily.")
    )

    assert [fact["medication_name"].lower() for fact in facts] == [
        "metformin",
        "warfarin",
    ]
    assert [(fact.get("dose_value"), fact.get("dose_unit")) for fact in facts] == [
        ("500", "mg"),
        ("5", "mg"),
    ]
    assert [fact.get("frequency") for fact in facts] == ["daily", "twice daily"]


def test_implicit_negation_across_and_is_kept_together_for_review():
    text = "Denies cough and fever."
    spans = list(atomic_spans(text))
    facts = extract(transcript(text))

    assert [span[2] for span in spans] == [text]
    assert len(facts) == 1
    assert facts[0]["assertion"] == "uncertain"


def test_medication_action_and_explicit_uncertainty_stay_with_their_drugs():
    facts = extract(
        transcript("Maybe start metformin 500 mg daily and stop warfarin 5 mg daily.")
    )

    assert [fact["medication_name"].lower() for fact in facts] == [
        "metformin",
        "warfarin",
    ]
    assert [fact["action"] for fact in facts] == ["start", "stop"]
    assert [fact["uncertainty"] for fact in facts] == ["possible", "certain"]
    assert [fact["assertion"] for fact in facts] == ["uncertain", "affirmed"]
    assert [fact["dose_value"] for fact in facts] == ["500", "5"]
