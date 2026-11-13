from uuid import uuid4

from services.review.clinical import extract


def extract_one(text):
    return extract({"segments": [{"segment_id": str(uuid4()), "text": text}]})


def test_explicit_allergen_reaction_and_spoken_severity_are_captured():
    fact = extract_one("Severe hives as a reaction to penicillin.")[0]

    assert fact["category"] == "allergy"
    assert fact["allergen"] == "penicillin"
    assert fact["allergy_reaction"] == "hives"
    assert fact["allergy_severity"] == "severe"


def test_allergy_absence_wording_does_not_invent_an_allergen_or_reaction():
    fact = extract_one("No known allergies.")[0]

    assert fact["category"] == "allergy"
    assert fact["assertion"] == "negated"
    assert fact.get("allergen") is None
    assert fact.get("allergy_reaction") is None
    assert fact["allergy_severity"] == "unknown"


def test_silence_about_allergies_creates_no_allergy_fact():
    facts = extract_one("Patient reports cough.")

    assert all(fact["category"] != "allergy" for fact in facts)


def test_allergy_without_severity_words_keeps_severity_unknown():
    fact = extract_one("Allergy to latex with rash.")[0]

    assert fact["allergen"] == "latex"
    assert fact["allergy_reaction"] == "rash"
    assert fact["allergy_severity"] == "unknown"
