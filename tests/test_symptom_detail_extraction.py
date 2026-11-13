from uuid import uuid4

from services.review.clinical import extract


def extract_facts(text):
    return extract({"segments": [{"segment_id": str(uuid4()), "text": text}]})


def test_symptom_severity_site_onset_duration_and_course_remain_separate():
    fact = extract_facts(
        "Severe left knee pain since yesterday for 2 days, worsening."
    )[0]

    assert fact["category"] == "symptom"
    assert fact["assertion"] == "affirmed"
    assert fact["anatomical_site"] == "knee"
    assert fact["laterality"] == "left"
    assert fact["symptom_onset"] == "yesterday"
    assert fact["symptom_duration"] == "2 days"
    assert fact["symptom_severity"] == "severe"
    assert fact["symptom_course"] == "worsening"


def test_distinct_laterality_and_sites_split_into_source_linked_facts():
    facts = extract_facts("Left knee pain and right shoulder pain.")

    assert [(fact["anatomical_site"], fact["laterality"]) for fact in facts] == [
        ("knee", "left"),
        ("shoulder", "right"),
    ]
    for fact in facts:
        evidence = fact["evidence"]
        assert evidence["end_char"] - evidence["start_char"] == len(evidence["quote"])


def test_negated_possible_and_questioned_symptoms_keep_distinct_assertions():
    facts = extract_facts("No cough. Maybe fever. Could this be pain?")

    assert [fact["assertion"] for fact in facts] == [
        "negated",
        "uncertain",
        "uncertain",
    ]
    assert [fact["uncertainty"] for fact in facts] == [
        "certain",
        "possible",
        "questioned",
    ]
    assert [fact["symptom_severity"] for fact in facts] == [
        "unknown",
        "unknown",
        "unknown",
    ]
