from pydantic import BaseModel

from services.domain_contracts import NoteVersion, TranscriptVersion, validate_record


def test_persistence_records_are_typed_and_json_serializable():
    assert issubclass(NoteVersion, BaseModel)
    assert issubclass(TranscriptVersion, BaseModel)
    assert callable(validate_record)
    schema = NoteVersion.model_json_schema()
    assert 'properties' in schema and 'schema_version' in schema['properties']
