from uuid import uuid4

from services.review.clinical import extract


def measurements(text):
    return extract({"segments": [{"segment_id": str(uuid4()), "text": text}]})


def test_blood_pressure_keeps_raw_value_unit_and_stated_time():
    fact = measurements("Measured blood pressure 120/80 mmHg this morning.")[0]

    assert fact["category"] == "measurement"
    assert fact["measurement_value"] == "120/80"
    assert fact["measurement_unit"] == "mmHg"
    assert fact["measurement_time"] == "this morning"
    assert fact["measurement_source_confidence"] == "medium"


def test_approximate_temperature_is_not_silently_normalized():
    fact = measurements("Temperature about 37.5 C yesterday.")[0]

    assert fact["measurement_value"] == "37.5"
    assert fact["measurement_unit"] == "C"
    assert fact["measurement_time"] == "yesterday"
    assert fact["measurement_source_confidence"] == "low"


def test_missing_unit_or_source_confidence_remains_unknown():
    fact = measurements("Temperature 98.6.")[0]

    assert fact["measurement_value"] == "98.6"
    assert fact.get("measurement_unit") is None
    assert fact["measurement_source_confidence"] == "unknown"
